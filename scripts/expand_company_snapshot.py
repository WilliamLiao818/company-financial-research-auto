"""Expand public-company snapshots without changing existing annual statement rows.

SEC Company Facts is preferred. A complete Yahoo annual statement series is used
when SEC standard tags are incomplete; sources are never silently mixed per row.
Raw responses and an audit manifest are cached outside the deployable application.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import urllib.parse
import urllib.request

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research import validate_financials
from sec_connector import company_facts_to_frame

FIELDS = {
    "revenue": "annualTotalRevenue", "gross_profit": "annualGrossProfit",
    "operating_income": "annualOperatingIncome", "net_income": "annualNetIncome",
    "operating_cash_flow": "annualOperatingCashFlow", "capex": "annualCapitalExpenditure",
    "assets": "annualTotalAssets", "liabilities": "annualTotalLiabilitiesNetMinorityInterest",
    "equity": "annualStockholdersEquity",
}

# Standard feeds omit these figures. Values are gross cash purchases, not STM's
# grant-adjusted Net Capex. Airbnb annual amounts sum the four disclosed quarters.
PRIMARY_CAPEX_SUPPLEMENTS = {
    "ABNB": {
        "values": {2023: 47e6, 2024: 34e6, 2025: 33e6},
        "accession": "0001193125-26-048670",
        "label": "Primary filing table: Purchases of property and equipment; annual sum of four reported quarters",
        "url": "https://s26.q4cdn.com/656283129/files/doc_financials/2025/q4/Airbnb_Q4-2025-Shareholder-Letter-Final.pdf",
        "locator": "Page 25, Free Cash Flow Reconciliation",
    },
    "STM": {
        "values": {2023: 4439e6, 2024: 3088e6, 2025: 2111e6},
        "accession": "0000932787-26-000009",
        "label": "Primary filing table: Payment for purchase of tangible assets",
        "url": "https://www.sec.gov/Archives/edgar/data/932787/000093278726000009/stm-20251231.htm",
        "locator": "F-8, Consolidated Statements of Cash Flows",
    },
}


def supplement_capex(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ["capex_xbrl_tag", "capex_accession"]:
        if column not in result:
            result[column] = ""
    for ticker, supplement in PRIMARY_CAPEX_SUPPLEMENTS.items():
        for year, value in supplement["values"].items():
            missing = (result.ticker == ticker) & (result.fiscal_year == year) & result.capex.isna()
            result.loc[missing, "capex"] = value
            result.loc[missing, "capex_xbrl_tag"] = supplement["label"]
            result.loc[missing, "capex_accession"] = supplement["accession"]
    return result


def read_json(url: str, cache: Path) -> dict:
    if cache.exists():
        return json.loads(cache.read_text())
    last_error = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (LiaoResearch; https://liaoresearch.com)", "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=35) as response:
                payload = json.load(response)
            cache.write_text(json.dumps(payload))
            return payload
        except Exception as error:
            last_error = error
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Public source unavailable: {url}: {last_error}")


def atomic_csv(frame: pd.DataFrame, output: Path) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        frame.to_csv(temporary, index=False)
        temporary.chmod(0o644)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def normalize_metadata(frame: pd.DataFrame, tickers: list[str], cache: Path) -> tuple[pd.DataFrame, list[dict]]:
    """Normalize fiscal dates with primary filing evidence.

Yahoo sometimes normalizes a 52/53-week fiscal end to calendar month-end. Where
reported annual revenue matches a nearby SEC annual period, retain the actual
statement end. For early-January 52/53-week closes, use the prior year only when
the earliest annual filing confirms that label. Other FY labels retain the end
year: SEC's `fy` can be incorrect or refer to a later comparative filing.
Financial values and their provider remain unchanged.
    """
    from research_catalog import COMPANY_NAMES
    result = frame.copy()
    corrections = []
    for ticker in tickers:
        result.loc[result.ticker == ticker, "company"] = COMPANY_NAMES[ticker]
        path = cache / f"{ticker}-sec.json"
        if not path.exists():
            continue
        raw = json.loads(path.read_text())
        candidates = []
        for namespace in raw.get("facts", {}).values():
            for tag in ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet", "Revenue", "RevenueFromContractsWithCustomers", "RevenueFromSaleOfGoods"]:
                for currency, values in namespace.get(tag, {}).get("units", {}).items():
                    for item in values:
                        if item.get("form") not in {"10-K", "20-F", "40-F"} or item.get("fp") != "FY" or not item.get("start") or not item.get("fy"):
                            continue
                        days = (date.fromisoformat(item["end"]) - date.fromisoformat(item["start"])).days
                        if 300 <= days <= 400:
                            candidates.append({**item, "currency": currency})
        for index, row in result.loc[result.ticker == ticker].iterrows():
            end = date.fromisoformat(str(row.fiscal_year_end))
            matches = [item for item in candidates if item["currency"] == row.currency and abs((date.fromisoformat(item["end"]) - end).days) <= 7 and abs(float(item["val"]) - float(row.revenue)) <= max(1, abs(float(row.revenue)) * .00001)]
            if not matches:
                continue
            original = min(matches, key=lambda item: (abs((date.fromisoformat(item["end"]) - end).days), item.get("filed", "9999")))
            actual_end = date.fromisoformat(original["end"])
            earliest = min((item for item in candidates if item["end"] == original["end"] and item["currency"] == row.currency), key=lambda item: item.get("filed", "9999"))
            fiscal_year = actual_end.year
            if actual_end.month == 1 and actual_end.day <= 7 and int(earliest["fy"]) == actual_end.year - 1:
                fiscal_year = int(earliest["fy"])
            if int(row.fiscal_year) != fiscal_year or str(row.fiscal_year_end) != original["end"]:
                corrections.append({"ticker": ticker, "provider_period": str(row.fiscal_year_end), "fiscal_year": fiscal_year, "actual_period_end": original["end"], "accession": original.get("accn", "")})
                result.loc[index, "fiscal_year"] = fiscal_year
                result.loc[index, "fiscal_year_end"] = original["end"]
    return result, corrections


def yahoo_annual(ticker: str, company: str, as_of: pd.Timestamp, cache: Path) -> pd.DataFrame:
    params = urllib.parse.urlencode({"symbol": ticker, "type": ",".join(FIELDS.values()), "period1": int((as_of - pd.DateOffset(years=7)).timestamp()), "period2": int(as_of.timestamp())})
    url = f"https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{ticker}?{params}"
    payload = read_json(url, cache / f"{ticker}-annual-yahoo.json")
    periods = {}
    for result in payload.get("timeseries", {}).get("result", []):
        for field, provider_field in FIELDS.items():
            for item in result.get(provider_field, []):
                end = str(item.get("asOfDate", ""))
                value = item.get("reportedValue", {}).get("raw")
                if not end or value is None or pd.Timestamp(end, tz="UTC") >= as_of:
                    continue
                row = periods.setdefault(end, {"currency": item.get("currencyCode", "")})
                row[field] = abs(float(value)) if field == "capex" else float(value)
    selected = sorted(end for end, row in periods.items() if row.get("revenue") is not None)[-5:]
    rows = []
    for end in selected:
        row = periods[end]
        rows.append({"ticker": ticker, "company": company, "fiscal_year": int(end[:4]), "fiscal_year_end": end, "filed": "", "source_url": f"https://finance.yahoo.com/quote/{ticker}/financials/", "cost_of_revenue": row["revenue"] - row["gross_profit"] if row.get("gross_profit") is not None else None, **row})
    return pd.DataFrame(rows)


def annual(ticker: str, meta: dict, as_of: pd.Timestamp, cache: Path) -> tuple[pd.DataFrame, dict]:
    cik = str(meta["cik_str"]).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    note = {"ticker": ticker, "cik": cik}
    sec = pd.DataFrame()
    try:
        raw = read_json(url, cache / f"{ticker}-sec.json")
        sec = company_facts_to_frame(raw, ticker=ticker, years=5)
        sec = sec.loc[(pd.to_datetime(sec["fiscal_year_end"], utc=True) < as_of) & (pd.to_datetime(sec["filed"], utc=True) < as_of)]
    except Exception as error:
        note["sec_error"] = str(error)
    essential = ["revenue", "operating_income", "net_income", "operating_cash_flow", "capex", "assets", "liabilities", "equity"]
    complete = len(sec) >= 2 and sec[essential].notna().all().all()
    current = len(sec) and pd.Timestamp(sec["fiscal_year_end"].max(), tz="UTC") >= as_of - pd.DateOffset(months=19)
    selected = sec
    if not (complete and current):
        try:
            yahoo = yahoo_annual(ticker, meta["title"], as_of, cache)
            if len(yahoo) >= 2:
                selected = yahoo
                note["fallback_reason"] = "Incomplete standard SEC tags or annual history; full normalized statement series retained with provider source."
        except Exception as error:
            note["yahoo_error"] = str(error)
    if len(selected) < 2:
        raise ValueError(f"{ticker}: fewer than two reported annual periods: {note}")
    # Identity is normalized against the application catalog once available.
    from research_catalog import COMPANY_NAMES
    selected["company"] = COMPANY_NAMES.get(ticker, meta["title"])
    note.update({"periods": len(selected), "latest_period": str(selected["fiscal_year_end"].max()), "currency": str(selected["currency"].iloc[-1]), "source_url": str(selected["source_url"].iloc[-1]), "missing_fields": {key: int(selected.get(key, pd.Series(dtype=float)).isna().sum()) for key in essential}})
    return selected, note


def market(ticker: str, as_of: pd.Timestamp, cache: Path) -> pd.DataFrame:
    params = urllib.parse.urlencode({"period1": int((as_of - pd.DateOffset(years=10)).timestamp()), "period2": int(as_of.timestamp()), "interval": "1mo", "events": "div,splits", "includeAdjustedClose": "true"})
    raw = read_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?{params}", cache / f"{ticker}-market.json")
    result = raw.get("chart", {}).get("result")
    if not result:
        raise ValueError(f"{ticker}: no market series")
    block = result[0]
    adjusted = block.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])
    # Never label raw closing prices as adjusted prices.
    if not adjusted:
        raise ValueError(f"{ticker}: source did not supply adjusted closing prices")
    frame = pd.DataFrame({"date": pd.to_datetime(block["timestamp"], unit="s", utc=True), "series": ticker, "adjusted_close": adjusted}).dropna()
    frame = frame.loc[(frame["date"] < as_of) & (frame["adjusted_close"] > 0)].copy()
    frame["date"] = frame["date"].dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    frame = frame.drop_duplicates("date", keep="last").sort_values("date")
    if len(frame) < 2:
        raise ValueError(f"{ticker}: insufficient adjusted price history")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", required=True)
    parser.add_argument("--as-of", required=True, help="UTC observation cutoff, YYYY-MM-DD")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--ticker-map", type=Path, required=True)
    parser.add_argument("--financial-only", action="store_true")
    parser.add_argument("--market-only", action="store_true")
    args = parser.parse_args()
    as_of = pd.Timestamp(args.as_of, tz="UTC")
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    ticker_map = {row["ticker"]: row for row in json.loads(args.ticker_map.read_text()).values()}
    tickers = sorted(set(args.tickers.split(",")))
    existing = pd.read_csv(ROOT / "data/financials.csv")
    notes = []
    if not args.market_only:
        frames = []
        for ticker in tickers:
            if ticker in set(existing["ticker"]):
                continue
            frame, note = annual(ticker, ticker_map[ticker], as_of, args.cache_dir)
            frames.append(frame.reindex(columns=existing.columns))
            notes.append(note)
            print(f"Annual {ticker}: {note['periods']} periods through {note['latest_period']} ({note['currency']}); {note['source_url']}", flush=True)
        combined = pd.concat([existing, *frames], ignore_index=True)
        combined, corrections = normalize_metadata(combined, tickers, args.cache_dir)
        combined = supplement_capex(combined)
        errors = validate_financials(combined)
        if errors:
            raise ValueError(errors)
        atomic_csv(combined, ROOT / "data/financials.csv")
        (args.cache_dir / "annual-audit.json").write_text(json.dumps({"checked_at": datetime.now(timezone.utc).isoformat(), "as_of": args.as_of, "companies": notes, "fiscal_metadata_corrections": corrections, "primary_capex_supplements": PRIMARY_CAPEX_SUPPLEMENTS}, indent=2))
    if not args.financial_only:
        symbols = sorted(set(existing["ticker"]) | set(tickers) | {"SPY", "QQQ"})
        frames = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(market, ticker, as_of, args.cache_dir): ticker for ticker in symbols}
            for future in as_completed(futures):
                frame = future.result()
                frames.append(frame)
                print(f"Market {futures[future]}: {len(frame)} months", flush=True)
        combined = pd.concat(frames, ignore_index=True).sort_values(["series", "date"])
        atomic_csv(combined, ROOT / "data/market_performance.csv")
    print("Snapshot expansion completed.", flush=True)


if __name__ == "__main__":
    main()
