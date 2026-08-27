from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping

import pandas as pd


SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

METRICS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "gross_profit": ["GrossProfit"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
}


class SecInputError(ValueError):
    """The identifier or uploaded SEC payload is invalid or unsupported."""


class SecConfigurationError(RuntimeError):
    """Required SEC request identification is missing."""


class SecConnectionError(RuntimeError):
    """SEC data could not be fetched; no fallback values were generated."""


def normalize_cik(value: str | int) -> str:
    raw = str(value).strip()
    if raw.upper().startswith("CIK"):
        raw = raw[3:]
    if not raw.isdigit() or not 1 <= len(raw) <= 10:
        raise SecInputError("CIK must contain 1 to 10 digits, optionally prefixed by CIK.")
    return raw.zfill(10)


def sec_user_agent(value: str | None = None) -> str:
    configured = (value if value is not None else os.environ.get("SEC_USER_AGENT", "")).strip()
    if not configured or "@" not in configured:
        raise SecConfigurationError(
            "Online SEC loading requires SEC_USER_AGENT with an identifiable name and public contact email. "
            "Use the frozen demo or upload a saved SEC JSON/financial CSV when it is not configured."
        )
    return configured


def _fetch_json(url: str, user_agent: str | None = None) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": sec_user_agent(user_agent), "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise SecConnectionError(
            f"Could not load public SEC data from {url}. Check the network and identifier; no values were guessed."
        ) from error


def resolve_sec_identifier(identifier: str, user_agent: str | None = None) -> dict[str, str]:
    value = identifier.strip()
    if not value:
        raise SecInputError("Enter a ticker or CIK.")
    if value.isdigit() or value.upper().startswith("CIK"):
        cik = normalize_cik(value)
        return {"ticker": f"CIK{cik}", "cik": cik, "company": f"SEC registrant CIK {cik}"}

    ticker = value.upper()
    if not ticker.replace(".", "").replace("-", "").isalnum():
        raise SecInputError(f"Unsupported ticker format: {identifier}")
    payload = _fetch_json(SEC_TICKER_MAP_URL, user_agent)
    for item in payload.values():
        if str(item.get("ticker", "")).upper() == ticker:
            return {
                "ticker": ticker,
                "cik": normalize_cik(item["cik_str"]),
                "company": str(item.get("title", ticker)),
            }
    raise SecInputError(f"Ticker {ticker} was not found in the SEC company ticker file.")


def select_annual_facts(payload: Mapping, tags: list[str]) -> dict[str, dict]:
    """Select the latest-filed annual fact per period, preserving preferred tag order."""
    us_gaap = payload.get("facts", {}).get("us-gaap", {})
    selected: dict[str, dict] = {}
    for tag in tags:
        candidates = us_gaap.get(tag, {}).get("units", {}).get("USD", [])
        by_period: dict[str, dict] = {}
        for item in candidates:
            if (
                item.get("form") not in {"10-K", "20-F", "40-F"}
                or item.get("fp") != "FY"
                or not item.get("end")
            ):
                continue
            period = str(item["end"])
            current = by_period.get(period)
            if current is None or str(item.get("filed", "")) > str(current.get("filed", "")):
                by_period[period] = dict(item)
        for period, item in by_period.items():
            if period not in selected:
                item["_xbrl_tag"] = tag
                selected[period] = item
    return selected


def company_facts_to_frame(
    payload: Mapping,
    *,
    ticker: str | None = None,
    years: int = 5,
    source_url: str | None = None,
) -> pd.DataFrame:
    """Normalize an in-memory SEC Company Facts payload without filling absent facts."""
    if years < 1 or years > 20:
        raise SecInputError("Years must be between 1 and 20.")
    if not isinstance(payload, Mapping):
        raise SecInputError("SEC Company Facts JSON must be an object.")
    us_gaap = payload.get("facts", {}).get("us-gaap")
    if not isinstance(us_gaap, Mapping):
        raise SecInputError("Uploaded JSON does not contain facts.us-gaap Company Facts data.")

    cik = normalize_cik(payload.get("cik", ""))
    entity_name = str(payload.get("entityName", "")).strip() or f"SEC registrant CIK {cik}"
    display_ticker = (ticker or f"CIK{cik}").strip().upper()
    fact_url = source_url or SEC_COMPANY_FACTS_URL.format(cik=cik)
    metric_values = {name: select_annual_facts(payload, tags) for name, tags in METRICS.items()}
    periods = sorted(metric_values["revenue"])[-years:]
    if not periods:
        raise SecInputError("No annual USD revenue facts matched the supported standard XBRL tags.")

    rows: list[dict[str, object]] = []
    for period_end in periods:
        revenue_fact = metric_values["revenue"].get(period_end, {})
        # Company Facts may attach the latest filing's `fy` value to prior
        # comparative periods. The statement end date is the stable period
        # identity for an annual research series.
        fiscal_year = int(period_end[:4])
        row: dict[str, object] = {
            "ticker": display_ticker,
            "company": entity_name,
            "cik": cik,
            "fiscal_year": fiscal_year,
            "fiscal_year_end": period_end,
            "filed": revenue_fact.get("filed", ""),
            "form": revenue_fact.get("form", ""),
            "accession": revenue_fact.get("accn", ""),
            "source_url": fact_url,
            "input_source": "sec_company_facts",
        }
        for metric, values in metric_values.items():
            fact = values.get(period_end)
            row[metric] = fact.get("val") if fact else None
            row[f"{metric}_xbrl_tag"] = fact.get("_xbrl_tag", "") if fact else ""
            row[f"{metric}_accession"] = fact.get("accn", "") if fact else ""
        if row["gross_profit"] is None and row["revenue"] is not None and row["cost_of_revenue"] is not None:
            row["gross_profit"] = float(row["revenue"]) - float(row["cost_of_revenue"])
            row["gross_profit_xbrl_tag"] = "Derived: Revenue less cost of revenue"
        rows.append(row)
    return pd.DataFrame(rows)


def fetch_company_facts(identifier: str, *, years: int = 5, user_agent: str | None = None) -> pd.DataFrame:
    resolved = resolve_sec_identifier(identifier, user_agent)
    source_url = SEC_COMPANY_FACTS_URL.format(cik=resolved["cik"])
    payload = _fetch_json(source_url, user_agent)
    ticker = resolved["ticker"] if not resolved["ticker"].startswith("CIK") else None
    return company_facts_to_frame(payload, ticker=ticker, years=years, source_url=source_url)
