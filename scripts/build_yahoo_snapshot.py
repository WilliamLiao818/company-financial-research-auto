from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_catalog import COMPANY_NAMES  # noqa: E402


YAHOO_TIMESERIES_URL = "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}"
YAHOO_FIELDS = {
    "revenue": "annualTotalRevenue",
    "gross_profit": "annualGrossProfit",
    "operating_income": "annualOperatingIncome",
    "net_income": "annualNetIncome",
    "operating_cash_flow": "annualOperatingCashFlow",
    "capex": "annualCapitalExpenditure",
    "assets": "annualTotalAssets",
    "liabilities": "annualTotalLiabilitiesNetMinorityInterest",
    "equity": "annualStockholdersEquity",
}
OUTPUT_COLUMNS = [
    "ticker",
    "company",
    "fiscal_year",
    "fiscal_year_end",
    "filed",
    "source_url",
    "currency",
    "revenue",
    "gross_profit",
    "cost_of_revenue",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "capex",
    "assets",
    "liabilities",
    "equity",
]


class YahooSnapshotError(RuntimeError):
    """Yahoo's normalized public financial statements could not be loaded."""


def _load_json(url: str, *, attempts: int = 5) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; LiaoResearch/2.1; public-company-research)",
        },
    )
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(min(2 ** attempt, 12))
    raise YahooSnapshotError(f"Could not load {url} after {attempts} attempts.") from last_error


def fetch_annual_financials(ticker: str, *, years: int = 5) -> pd.DataFrame:
    symbol = ticker.strip().upper()
    if symbol not in COMPANY_NAMES:
        raise YahooSnapshotError(f"{symbol} is not a prebuilt company ticker.")
    now = int(time.time())
    start = now - int(max(years + 2, 6) * 365.25 * 24 * 60 * 60)
    params = urllib.parse.urlencode(
        {
            "symbol": symbol,
            "type": ",".join(YAHOO_FIELDS.values()),
            "period1": start,
            "period2": now,
        }
    )
    url = f"{YAHOO_TIMESERIES_URL.format(symbol=urllib.parse.quote(symbol, safe=''))}?{params}"
    payload = _load_json(url)
    results = payload.get("timeseries", {}).get("result", [])
    if not results:
        detail = payload.get("timeseries", {}).get("error")
        raise YahooSnapshotError(f"No annual financial statements were returned for {symbol}: {detail}")

    by_period: dict[str, dict[str, object]] = {}
    currencies: dict[str, str] = {}
    reverse_fields = {provider_field: field for field, provider_field in YAHOO_FIELDS.items()}
    for result in results:
        provider_field = next((field for field in reverse_fields if field in result), None)
        if not provider_field:
            continue
        field = reverse_fields[provider_field]
        for observation in result.get(provider_field, []):
            period = str(observation.get("asOfDate", ""))
            raw = observation.get("reportedValue", {}).get("raw")
            if not period or raw is None:
                continue
            by_period.setdefault(period, {})[field] = abs(float(raw)) if field == "capex" else float(raw)
            currency = str(observation.get("currencyCode", "")).strip()
            if currency:
                currencies[period] = currency

    periods = sorted(period for period, facts in by_period.items() if facts.get("revenue") is not None)[-years:]
    if not periods:
        raise YahooSnapshotError(f"No annual revenue periods were returned for {symbol}.")

    rows: list[dict[str, object]] = []
    statement_url = f"https://finance.yahoo.com/quote/{urllib.parse.quote(symbol, safe='')}/financials/"
    for period in periods:
        facts = by_period[period]
        gross_profit = facts.get("gross_profit")
        revenue = facts.get("revenue")
        cost_of_revenue = (
            float(revenue) - float(gross_profit)
            if revenue is not None and gross_profit is not None
            else None
        )
        row = {
            "ticker": symbol,
            "company": COMPANY_NAMES[symbol],
            "fiscal_year": int(period[:4]),
            "fiscal_year_end": period,
            # The provider exposes the statement period but not the filing date.
            # Keep this blank rather than presenting an inferred date as a filed fact.
            "filed": "",
            "source_url": statement_url,
            "currency": currencies.get(period, "USD"),
            "cost_of_revenue": cost_of_revenue,
            **facts,
        }
        rows.append({column: row.get(column) for column in OUTPUT_COLUMNS})
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def _write_csv_atomically(frame: pd.DataFrame, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        frame.to_csv(temporary_path, index=False)
        temporary_path.chmod(0o644)
        temporary_path.replace(output)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a normalized annual snapshot from Yahoo Finance public statement data."
    )
    parser.add_argument(
        "--identifier",
        action="append",
        help="Prebuilt ticker. Repeat the flag or provide comma-separated tickers.",
    )
    parser.add_argument("--all-prebuilt", action="store_true", help="Refresh every prebuilt company.")
    parser.add_argument("--years", type=int, default=5, help="Latest annual periods to keep (1-5).")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.years <= 5:
        parser.error("--years must be between 1 and 5")
    if args.all_prebuilt and args.identifier:
        parser.error("--all-prebuilt cannot be combined with --identifier")
    identifiers = (
        list(COMPANY_NAMES)
        if args.all_prebuilt
        else list(
            dict.fromkeys(
                item.strip().upper()
                for entry in (args.identifier or [])
                for item in entry.split(",")
                if item.strip()
            )
        )
    )
    if not identifiers:
        parser.error("provide --identifier or --all-prebuilt")

    frames: list[pd.DataFrame] = []
    for identifier in identifiers:
        frame = fetch_annual_financials(identifier, years=args.years)
        frames.append(frame)
        print(f"Loaded {identifier}: {len(frame)} annual periods")
        time.sleep(0.2)
    output = pd.concat(frames, ignore_index=True)[OUTPUT_COLUMNS]
    _write_csv_atomically(output, args.output)
    print(f"Wrote {len(output)} company-year rows to {args.output}")


if __name__ == "__main__":
    main()
