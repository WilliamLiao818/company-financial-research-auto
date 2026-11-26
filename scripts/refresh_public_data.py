"""Update the public Company dataset. The workflow publishes the validated files in one commit."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data_health import read_json
from provider_quarter import choose_quarter, fetch_provider_quarter, provider_check_status
from market_data import BENCHMARKS, fetch_adjusted_monthly
from filing_index import ListedIndex
from news_connector import load_company_news_snapshot
from research import REPORTED_FACT_FIELDS, validate_financials
from research_catalog import COMPANY_NAMES, CIKS
from sec_connector import SEC_COMPANY_FACTS_URL, US_GAAP_METRICS, IFRS_METRICS, company_facts_to_frame
from scripts.expand_company_snapshot import atomic_csv, supplement_capex, yahoo_annual
from scripts.refresh_recent_news import _merge_stories, _refresh_company
from verified_filings import VERIFIED_ANNUALS, VERIFIED_ANNUAL_RELEASES, VERIFIED_QUARTERS

DATA = ROOT / "data"
CORE = ["revenue", "operating_income", "net_income", "capex", "operating_cash_flow", "assets"]
SEC_CONTACT = os.environ.get("SEC_CONTACT_EMAIL") or "https://github.com/WilliamLiao818/company-financial-research-auto/issues"


def write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def check_result(previous: dict, now: str, outcome: str, observed: str = "") -> dict:
    checked = previous.get("verified_at", "") if outcome in {"retained", "delayed"} else now
    return {"attempted_at": now, "verified_at": checked, "status": outcome,
            "as_of": observed or (previous.get("as_of", "") if outcome == "retained" else "")}


class Edgar:
    def __init__(self):
        self.blocked = False

    def get(self, url: str) -> dict:
        if self.blocked:
            raise RuntimeError("SEC access unavailable in this run")
        request = Request(url, headers={"User-Agent": f"Liao Research {SEC_CONTACT}", "Accept": "application/json"})
        for attempt in range(3):
            time.sleep(0.2)
            try:
                with urlopen(request, timeout=20) as response:
                    return json.load(response)
            except HTTPError as error:
                if error.code == 403:
                    self.blocked = True
                    raise
                if error.code == 429:
                    self.blocked = True
                    raise
                if error.code < 500 or attempt == 2:
                    raise
            except (URLError, TimeoutError):
                if attempt == 2:
                    raise
            time.sleep(2 ** attempt)


def filing_summary(payload: dict, cik: str, today: date) -> dict:
    if int(payload["cik"]) != int(cik):
        raise ValueError("Registrant mismatch")
    recent = payload["filings"]["recent"]
    entries = []
    for form, filed, accession, document in zip(
        recent["form"], recent["filingDate"], recent["accessionNumber"], recent["primaryDocument"], strict=True,
    ):
        if form.removesuffix("/A") not in {"10-K", "10-Q", "8-K", "20-F", "6-K", "40-F"}:
            continue
        if filed > today.isoformat() or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
            continue
        if not re.fullmatch(r"[\w.-]+", document):
            document = accession + "-index.htm"
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{document}"
        entries.append({"filed": filed, "form": form, "accession": accession, "url": url})
    if not entries:
        raise ValueError("Empty SEC submissions history")
    return max(entries, key=lambda row: (row["filed"], row["accession"]))


def quarter_summary(payload: dict, today: date, preferred_currency: str = "USD") -> dict:
    # Every figure must share currency, duration and accession. A six/nine-month
    # year-to-date figure or a derived fourth quarter never becomes a reported quarter.
    observed = {}
    for namespace, mapping in [("us-gaap", US_GAAP_METRICS), ("ifrs-full", IFRS_METRICS)]:
        concepts = payload.get("facts", {}).get(namespace, {})
        for field in ("revenue", "operating_income", "net_income"):
            for tag in mapping[field]:
                for currency, rows in concepts.get(tag, {}).get("units", {}).items():
                    if currency not in {"USD", "EUR", "TWD", "GBP", "JPY"}:
                        continue
                    for row in rows:
                        if row.get("form", "").removesuffix("/A") not in {"10-Q", "10-K", "20-F", "6-K", "8-K"}:
                            continue
                        if not all(row.get(k) for k in ("start", "end", "filed", "accn")) or row.get("val") is None:
                            continue
                        end = date.fromisoformat(row["end"])
                        if not 70 <= (end - date.fromisoformat(row["start"])).days <= 110 or not end <= date.fromisoformat(row["filed"]) <= today:
                            continue
                        key = (row["end"], row["filed"], row["accn"], currency, row["start"], row["form"])
                        observed.setdefault(key, {}).setdefault(field, row["val"] / 1_000_000)
    complete = [key for key, values in observed.items() if len(values) == 3 and all(map(math.isfinite, values.values()))]
    if not complete:
        return {}
    end, filed, accession, currency, start, form = key = max(complete, key=lambda key: (key[0], key[1], key[3] == preferred_currency))
    url = f"https://www.sec.gov/Archives/edgar/data/{int(payload['cik'])}/{accession.replace('-', '')}/{accession}-index.htm"
    return {"period_end": end, "period_start": start, "filed": filed, "label": f"Quarter to {end}",
            "accession": accession, "currency": currency, "unit": "millions", "form": form, "url": url, **observed[key]}


def merge_annual(saved: pd.DataFrame, fresh: pd.DataFrame, *, primary: bool, today: date) -> pd.DataFrame:
    """Retain verified rows unless the same period improves or a comparable new year arrives."""
    if fresh.empty or saved.empty:
        raise ValueError("Missing annual series")
    result = saved.copy()
    latest = result.sort_values("fiscal_year_end").iloc[-1]
    fresh = fresh.sort_values("fiscal_year_end")
    valid_source = False
    for _, row in fresh.iterrows():
        end = date.fromisoformat(row["fiscal_year_end"])
        if end > today or row["currency"] != latest["currency"]:
            continue
        if pd.isna(row["revenue"]) or row["revenue"] <= 0:
            continue
        if not all(math.isfinite(float(row[k])) for k in REPORTED_FACT_FIELDS if pd.notna(row.get(k))):
            continue
        difference = (pd.to_datetime(result.fiscal_year_end) - pd.Timestamp(end)).abs().dt.days
        matches = result.index[difference <= 7]
        if len(matches):
            i = matches[0]
            # A secondary provider must not rewrite primary disclosures or fixed reporting dates.
            complete = set(saved.loc[i, REPORTED_FACT_FIELDS].dropna().index) <= set(row.reindex(REPORTED_FACT_FIELDS).dropna().index)
            curated = ("/Archives/edgar/" in str(saved.at[i, "source_url"]) and pd.isna(saved.at[i, "accession"])) or (
                bool(pd.notna(saved.at[i, "capex_accession"])) and "Primary filing table" in str(saved.at[i, "capex_xbrl_tag"]))
            old_date = saved.at[i, "filed"]
            new_filed = str(row.get("filed", ""))
            ppe_tag = str(row.get("capex_xbrl_tag", "")) in {
                "PaymentsToAcquirePropertyPlantAndEquipment", "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"}
            later_primary = pd.notna(old_date) and new_filed > str(old_date) and ppe_tag
            can_replace = primary and complete and (not curated or later_primary) and (pd.isna(old_date) or new_filed >= str(old_date))
            if can_replace:
                replacement = row.reindex(saved.columns).copy()
                replacement["fiscal_year"] = saved.at[i, "fiscal_year"]
                result.loc[i] = replacement
            agrees = math.isclose(float(row["revenue"]), float(saved.at[i, "revenue"]), rel_tol=0.001, abs_tol=1)
            valid_source |= (saved.at[i, "fiscal_year_end"] == latest["fiscal_year_end"] and (can_replace or agrees))
            continue
        if end <= date.fromisoformat(latest["fiscal_year_end"]):
            continue
        if any(pd.isna(row.get(k)) for k in CORE):
            raise ValueError("New annual period lacks required comparable fields")
        candidate = row.reindex(result.columns).copy()
        years = round((end - date.fromisoformat(latest["fiscal_year_end"])).days / 365.25)
        candidate["fiscal_year"] = int(latest["fiscal_year"]) + years
        if years < 1 or candidate["fiscal_year"] in result.fiscal_year.values:
            raise ValueError("New annual period conflicts with fiscal year on file")
        result = pd.concat([result, candidate.to_frame().T], ignore_index=True)
        valid_source = True
    if not valid_source:
        raise ValueError("Source dates or currency lag the saved annual statements")
    return result


def verify_provider_periods(ticker, fresh, saved, submissions):
    # Financial providers often map a 52/53-week year to calendar month end.
    # New periods must match a real annual report before publication.
    recent = submissions.get("filings", {}).get("recent", {})
    candidates = [(end, filed, form, acc) for end, filed, form, acc in
                  zip(*(recent.get(k, []) for k in ("reportDate", "filingDate", "form", "accessionNumber")))
                  if form in {"10-K", "20-F", "40-F"} and end]
    for (symbol, year), record in VERIFIED_ANNUALS.items():
        if ticker == symbol:
            candidates.append(tuple(record[k] for k in ("fiscal_year_end", "filed", "form", "accession")))
    result = fresh.copy()
    for i, row in result.iterrows():
        end = date.fromisoformat(row.fiscal_year_end)
        matching = [c for c in candidates if abs((date.fromisoformat(c[0]) - end).days) <= 7]
        if matching:
            actual, filed, form, acc = min(matching, key=lambda c: abs((date.fromisoformat(c[0]) - end).days))
            result.loc[i, ["fiscal_year_end", "filed", "form", "accession"]] = [actual, filed, form, acc]
        elif (end - date.fromisoformat(saved.fiscal_year_end.max())).days > 7:
            raise ValueError("Provider reporting date awaits an annual filing")
    return result


def apply_filing_evidence(ticker, frame):
    frame = frame.copy()
    for (symbol, year), record in VERIFIED_ANNUAL_RELEASES.items():
        if symbol == ticker and record["fiscal_year_end"] > frame.fiscal_year_end.max() and record["currency"] == frame.currency.iloc[-1]:
            frame = pd.concat([frame, pd.DataFrame([record]).reindex(columns=frame.columns)], ignore_index=True)
    for (symbol, year), record in VERIFIED_ANNUALS.items():
        if symbol != ticker:
            continue
        matches = frame.index[(frame.fiscal_year == year) & (frame.currency == record["currency"])]
        for i in matches:
            if abs((date.fromisoformat(frame.at[i, "fiscal_year_end"]) - date.fromisoformat(record["fiscal_year_end"])).days) > 7:
                continue
            if not math.isclose(float(frame.at[i, "revenue"]), record["revenue"], rel_tol=0.00001):
                continue
            # Preserve later restatements.
            filed = frame.at[i, "filed"]
            if pd.notna(filed) and str(filed) > record["filed"] and not str(frame.at[i,"source_url"]).startswith("https://finance.yahoo."):
                continue
            for field in ("fiscal_year_end", "filed", "form", "accession", "revenue", "capex", "capex_xbrl_tag", "capex_accession"):
                frame.at[i, field] = record[field]
            frame.at[i, "revenue_accession"] = record["accession"]
            other_fields = record.get("statement_values", {})
            if (set(other_fields) == set(REPORTED_FACT_FIELDS) - {"revenue", "capex"}
                    and all(pd.notna(frame.at[i, key]) and math.isclose(float(frame.at[i, key]), amount, rel_tol=1e-9, abs_tol=1)
                            for key, amount in other_fields.items())):
                frame.at[i, "source_url"] = record["url"]
    return frame


def add_known_disclosures(ticker, packed):
    from research_catalog import LATEST_RESULTS_SNAPSHOTS
    records = [d for d in (LATEST_RESULTS_SNAPSHOTS.get(ticker), VERIFIED_QUARTERS.get(ticker)) if d and d.get("filed")]
    if records:
        newest = max(records, key=lambda entry: (entry["period_end"], entry["filed"]))
        packed["quarter"] = choose_quarter(packed.get("quarter", {}), newest)
    records += [record for (symbol, year), record in VERIFIED_ANNUALS.items() if symbol == ticker]
    records += [{**record, "url": record["source_url"]} for (symbol, year), record in VERIFIED_ANNUAL_RELEASES.items() if symbol == ticker]
    if records:
        recent = max(records, key=lambda row: row["filed"])
        if recent["filed"] > packed.get("filing", {}).get("filed", ""):
            packed["filing"] = {key: recent[key] for key in ("filed", "form", "accession", "url")}


def merge_distributed_filing(packed: dict, previous: dict, result: dict, now: str) -> dict:
    observed = result["filing"]
    known = packed.get("filing", {})
    watermark = date.fromisoformat(result["indexed_at"][:10])
    today = date.fromisoformat(now[:10])
    if watermark > today:
        raise ValueError("Filing index watermark in the future")
    later_known = observed["filed"] < known.get("filed", "")
    if observed["filed"] > known.get("filed", "") or not known:
        packed["filing"] = observed
    # Distinguish a successful lookup from a timely independent source.
    weekdays_since_update = max(0, len(pd.bdate_range(watermark + timedelta(days=1), today)))
    late = weekdays_since_update > 2 or later_known or watermark.isoformat() < previous.get("indexed_through", "")
    status = "delayed" if late else "distribution"
    return {**check_result(previous, now, status, packed["filing"]["filed"]),
            "indexed_through": watermark.isoformat(), "distribution_source": result["source"]}


def refresh_filings(symbols, ledger, now, data):
    statements = pd.read_csv(data / "financials.csv")
    for col in ("form", "accession", "revenue_accession"):
        if col not in statements:
            statements[col] = pd.Series(dtype="object")
    old_filings = read_json(data / "filings.json")
    edgar = Edgar()
    listed = ListedIndex()
    secondary_available = True
    replacements = {}
    today = date.fromisoformat(now[:10])
    with tempfile.TemporaryDirectory() as temporary:
        for ticker in symbols:
            company_status = ledger[ticker]
            saved = statements[statements.ticker == ticker].reset_index(drop=True)
            cik = CIKS[ticker]
            packed = old_filings.setdefault(ticker, {})
            add_known_disclosures(ticker, packed)
            submissions = {}
            previous_filing_check = company_status.get("filings", {})
            try:
                submissions = edgar.get(f"https://data.sec.gov/submissions/CIK{cik}.json")
                filing = filing_summary(submissions, cik, today)
                if filing["filed"] < packed.get("filing", {}).get("filed", ""):
                    raise ValueError("SEC submissions older than previous check")
                packed["filing"] = filing
                filing_check = check_result(previous_filing_check, now, "ok", filing["filed"])
            except Exception as exc:
                print(f"{ticker} filings: {type(exc).__name__}", flush=True)
                try:
                    distributed = listed.fetch(ticker, cik, today)
                    filing_check = merge_distributed_filing(packed, previous_filing_check, distributed, now)
                except Exception as index_error:
                    print(f"{ticker} independent filing index: {type(index_error).__name__}", flush=True)
                    filing_check = {**previous_filing_check, **check_result(previous_filing_check, now, "retained", packed.get("filing", {}).get("filed", ""))}
            company_status["filings"] = filing_check
            annual_status = "ok"
            quarter_status = "retained"
            try:
                raw = edgar.get(SEC_COMPANY_FACTS_URL.format(cik=cik))
                if int(raw["cik"]) != int(cik):
                    raise ValueError("SEC facts registrant mismatch")
                native = {"TSM": "TWD", "ASML": "EUR"}.get(ticker, str(saved.currency.iloc[-1]))
                quarter = quarter_summary(raw, today, preferred_currency=native)
                previous = packed.get("quarter", {})
                chosen = choose_quarter(previous, quarter)
                if chosen:
                    packed["quarter"] = chosen
                if quarter and chosen is quarter:
                    quarter_status = "ok"
                fresh = supplement_capex(company_facts_to_frame(raw, ticker=ticker))
                fresh["company"] = COMPANY_NAMES[ticker]
                # Preserve exact annual report evidence even when facts were later restated.
                fresh["source_url"] = [f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{acc}-index.htm"
                                       if re.fullmatch(r"\d{10}-\d{2}-\d{6}", str(acc)) else url
                                       for acc, url in zip(fresh.accession, fresh.source_url)]
                fresh = fresh[fresh.filed <= today.isoformat()]
                updated = merge_annual(saved, fresh, primary=True, today=today)
            except Exception as exc:
                print(f"{ticker} annual SEC: {type(exc).__name__}", flush=True)
                try:
                    if not secondary_available:
                        raise RuntimeError("Secondary provider unavailable in this run")
                    cutoff = pd.Timestamp(today + timedelta(days=1), tz="UTC")
                    fresh = yahoo_annual(ticker, COMPANY_NAMES[ticker], cutoff, Path(temporary))
                    fresh = verify_provider_periods(ticker, fresh, saved, submissions)
                    updated = merge_annual(saved, fresh, primary=False, today=today)
                    annual_status = "fallback"
                except Exception as fallback_error:
                    cause = fallback_error.__cause__
                    if isinstance(cause, HTTPError) and cause.code in {401, 403, 429}:
                        secondary_available = False
                    print(f"{ticker} annual fallback: {type(fallback_error).__name__}", flush=True)
                    annual_status, updated = "retained", saved
            quarter_end = packed.get("quarter", {}).get("period_end")
            next_due = quarter_end and (today - date.fromisoformat(quarter_end)).days >= 70
            if secondary_available and (quarter_status != "ok" or next_due):
                try:
                    provider = fetch_provider_quarter(ticker, today, Path(temporary))
                    current = packed.get("quarter", {})
                    chosen = choose_quarter(current, provider)
                    if chosen:
                        packed["quarter"] = chosen
                    if quarter_status != "ok" or chosen is provider:
                        quarter_status = provider_check_status(chosen, provider)
                except Exception as error:
                    if isinstance(error.__cause__, HTTPError) and error.__cause__.code in {401, 403, 429}:
                        secondary_available = False
                    print(f"{ticker} quarterly fallback: {type(error).__name__}", flush=True)
            current_quarter = packed.get("quarter", {})
            quarter_date = current_quarter.get("period_end", "")
            if current_quarter.get("period_precision") == "month":
                quarter_date = quarter_date[:7]
            company_status["quarterly"] = check_result(company_status.get("quarterly", {}), now, quarter_status, quarter_date)
            updated = apply_filing_evidence(ticker, updated)
            replacements[ticker] = updated
            company_status["financials"] = check_result(company_status.get("financials", {}), now, annual_status, updated.fiscal_year_end.max())
    combined = pd.concat([statements[~statements.ticker.isin(symbols)], *replacements.values()], ignore_index=True)
    errors = validate_financials(combined)
    if errors or combined.duplicated(["ticker", "fiscal_year"]).any():
        raise ValueError(f"Annual statements failed validation: {errors}")
    atomic_csv(combined.sort_values(["ticker", "fiscal_year"]), data / "financials.csv")
    write_json(data / "filings.json", old_filings)


def refresh_market(symbols, ledger, now, data):
    saved = pd.read_csv(data / "market_performance.csv", dtype={"date": str})
    if "observation_date" not in saved:
        saved["observation_date"] = ""
    all_symbols = [*symbols, *BENCHMARKS]
    parts = [saved[~saved.series.isin(all_symbols)]]
    def update(symbol):
        existing = saved[saved.series == symbol]
        try:
            frame = fetch_adjusted_monthly(symbol, attempts=3)
            if symbol == "SNDK":
                frame = frame.loc[frame.date >= "2025-02-01"]
            frame = frame.copy()
            frame["date"] = frame.date.dt.strftime("%Y-%m-%d")
            cutoff = (pd.Timestamp(now) - pd.DateOffset(years=10) + pd.DateOffset(months=1)).strftime("%Y-%m")
            expected = set(existing.loc[existing.date.str[:7] >= cutoff, "date"])
            if not expected <= set(frame.date) or frame.date.max() < existing.date.max():
                raise ValueError("Historical series is incomplete")
            observed = frame.observation_date.max()
            old_observed = ledger.get(symbol, {}).get("market", {}).get("as_of", "")
            if observed < old_observed:
                raise ValueError("Last quote predates the previously verified close")
            frame["series"] = symbol
            return symbol, frame.reindex(columns=saved.columns), "ok", observed
        except Exception as exc:
            print(f"{symbol} price: {type(exc).__name__}: {exc}", flush=True)
            return symbol, existing, "retained", ""
    with ThreadPoolExecutor(max_workers=3) as workers:
        results = list(workers.map(update, all_symbols))
        session = max((observed for symbol, _, status, observed in results if symbol in BENCHMARKS and status == "ok"), default="")
        for symbol, frame, status, observed in results:
            if status == "ok" and session and observed < session:
                status = "lagging"
            target = ledger.setdefault(symbol, {})
            target["market"] = check_result(target.get("market", {}), now, status, observed)
            parts.append(frame)
    result = pd.concat(parts, ignore_index=True).sort_values(["series", "date"])
    if result.duplicated(["series", "date"]).any() or not set(all_symbols) <= set(result.series):
        raise ValueError("Duplicate or missing market series")
    atomic_csv(result, data / "market_performance.csv")


def refresh_news(symbols, ledger, now, data):
    path = data / "recent_news.json"
    payload = read_json(path)
    companies = payload["companies"]
    def update(ticker):
        try:
            new = _refresh_company((ticker, COMPANY_NAMES[ticker]), limit=4, window_days=90)[1]
            status = "ok"
        except Exception as exc:
            print(f"{ticker} news: {type(exc).__name__}", flush=True)
            new, status = [], "retained"
        old = load_company_news_snapshot(ticker, limit=4, path=path)
        stories = _merge_stories(new, old, limit=4)
        return ticker, stories, status
    with ThreadPoolExecutor(max_workers=4) as workers:
        for ticker, stories, status in workers.map(update, symbols):
            companies[ticker] = stories
            observed = max((story["date"] for story in stories), default="")
            ledger[ticker]["news"] = check_result(ledger[ticker].get("news", {}), now, status, observed)
    write_json(path, {"generated_at": now, "window_days": 90, "companies": companies})


def unavailable_feeds(ledger: dict, fields: list[str], symbols: list[str]) -> set[str]:
    """A complete source outage means every requested company had to keep prior data."""
    return {field for field in fields
            if all(ledger.get(ticker, {}).get(field, {}).get("status") == "retained" for ticker in symbols)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feeds", choices=["filings", "market", "news", "all"], default="all")
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--ticker", action="append", choices=sorted(COMPANY_NAMES))
    args = parser.parse_args()
    symbols = sorted(set(args.ticker or COMPANY_NAMES))
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    path = args.data_dir / "refresh_status.json"
    ledger = read_json(path).get("companies", {})
    fields = ["filings", "financials", "quarterly", "market", "news"] if args.feeds == "all" else (
        ["filings", "financials", "quarterly"] if args.feeds == "filings" else [args.feeds])
    previous_outages = unavailable_feeds(ledger, fields, symbols)
    for symbol in symbols:
        ledger.setdefault(symbol, {})
    for name, refresh in [("filings", refresh_filings), ("market", refresh_market), ("news", refresh_news)]:
        if args.feeds in (name, "all"):
            refresh(symbols, ledger, now, args.data_dir)
    write_json(path, {"generated_at": now, "companies": ledger})
    for field in fields:
        following = [*symbols, *BENCHMARKS] if field == "market" else symbols
        if any(ledger[s][field]["attempted_at"] != now for s in following):
            raise RuntimeError(f"Incomplete refresh ledger for {field}")
        kept = [s for s in following if ledger[s][field]["status"] in {"retained", "lagging", "delayed"}]
        message = f"{field}: {len(following)-len(kept)}/{len(following)} checked"
        if kept:
            message += " · checks require attention for " + ", ".join(kept)
            if os.getenv("GITHUB_ACTIONS") == "true":
                print("::warning::" + message, flush=True)
        print(message, flush=True)
        if os.getenv("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
                print("- " + message, file=summary)
    if os.getenv("GITHUB_OUTPUT"):
        new_outages = unavailable_feeds(ledger, fields, symbols) - previous_outages
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            print("new_outages=" + ", ".join(sorted(new_outages)), file=output)


if __name__ == "__main__":
    main()
