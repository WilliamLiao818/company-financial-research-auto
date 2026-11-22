"""Reported quarterly observations. Provider month labels may differ from issuer fiscal dates."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from math import isfinite
from pathlib import Path
from urllib.parse import urlencode


FIELDS = {
    "quarterlyTotalRevenue": "revenue",
    "quarterlyOperatingIncome": "operating_income",
    "quarterlyNetIncome": "net_income",
}


def choose_quarter(saved: dict, incoming: dict) -> dict:
    if not saved.get("period_end"):
        return incoming if incoming.get("period_end") else saved
    if not incoming.get("period_end"):
        return saved
    interval = (date.fromisoformat(incoming["period_end"]) - date.fromisoformat(saved["period_end"])).days
    saved_primary = saved.get("source_kind") != "provider"
    incoming_primary = incoming.get("source_kind") != "provider"
    if saved_primary != incoming_primary and abs(interval) <= 31:
        return incoming if incoming_primary else saved
    if interval:
        return incoming if interval > 0 else saved
    if incoming_primary:
        return incoming if (incoming.get("filed") or "") >= (saved.get("filed") or "") else saved
    if incoming["currency"] != saved["currency"]:
        return saved
    return incoming if all(incoming.get(field) is not None for field in FIELDS.values() if saved.get(field) is not None) else saved


def provider_check_status(chosen: dict, provider: dict) -> str:
    if not provider or not chosen:
        return "retained"
    if chosen is provider:
        return "fallback"
    difference = (date.fromisoformat(chosen["period_end"]) - date.fromisoformat(provider["period_end"])).days
    if chosen.get("source_kind") != "provider" and abs(difference) <= 31:
        return "fallback"  # The provider was checked; issuer figures retain priority for this quarter.
    return "delayed" if difference > 0 else "retained"


def normalized_quarter(payload: dict, ticker: str, today: date) -> dict:
    if payload.get("timeseries", {}).get("error"):
        raise ValueError("The quarterly provider reported an error")
    rows = {}
    for series in payload.get("timeseries", {}).get("result") or []:
        if series.get("meta", {}).get("symbol") != [ticker]:
            raise ValueError("Quarterly provider symbol mismatch")
        for provider_key, metric in FIELDS.items():
            for item in series.get(provider_key) or []:
                if item.get("periodType") != "3M":
                    continue
                end = date.fromisoformat(item["asOfDate"])
                currency = item.get("currencyCode")
                raw = item.get("reportedValue", {}).get("raw")
                if end > today or currency not in {"USD", "TWD", "EUR", "JPY", "GBP"}:
                    continue
                if not isinstance(raw, (int, float)) or isinstance(raw, bool) or not isfinite(raw):
                    continue
                row = rows.setdefault((end, currency), {})
                if metric in row and row[metric] != raw / 1e6:
                    raise ValueError("Conflicting values for one quarterly field")
                row[metric] = raw / 1e6
    valid = [(end, currency) for (end, currency), row in rows.items() if row.get("revenue", 0) > 0]
    if not valid:
        return {}
    newest = max(end for end, currency in valid)
    candidates = [(end, currency) for end, currency in valid if end == newest]
    if len(candidates) != 1:
        raise ValueError("Ambiguous reporting currency for provider quarter")
    end, currency = candidates[0]
    return {
        "source_kind": "provider", "period_precision": "month", "period_start": None,
        "period_end": end.isoformat(), "label": f"Quarter · {end:%Y-%m}", "filed": None, "accession": None,
        "form": "Yahoo Finance quarterly financials", "url": f"https://finance.yahoo.com/quote/{ticker}/financials/",
        "currency": currency, "unit": "millions",
        **{field: rows[(end, currency)].get(field) for field in FIELDS.values()},
        "note": "Quarterly amounts follow Yahoo Finance's normalized financial statements. The provider identifies the reporting month.",
    }


def fetch_provider_quarter(ticker: str, today: date, cache: Path) -> dict:
    from scripts.expand_company_snapshot import read_json
    until = datetime.combine(today + timedelta(days=1), time.min, tzinfo=timezone.utc)
    params = urlencode({
        "symbol": ticker, "type": ",".join(FIELDS),
        "period1": int((until - timedelta(days=540)).timestamp()), "period2": int(until.timestamp()),
    })
    url = f"https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{ticker}?{params}"
    return normalized_quarter(read_json(url, cache / f"{ticker}-quarterly-yahoo.json"), ticker, today)
