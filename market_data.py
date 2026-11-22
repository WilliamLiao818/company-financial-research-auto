from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd


BENCHMARKS = {"SPY": "SPY", "QQQ": "QQQ"}
SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "market_performance.csv"
PERFORMANCE_NOTES = {
    # GE's April 2, 2024 announcement and Danaher's September 30, 2023
    # separation release confirm these changes in business perimeter.
    "GE": (
        "GE's earlier trading history includes the former conglomerate before the "
        "GE HealthCare and GE Vernova separations. Adjusted historical performance "
        "does not represent a decade of the current standalone aerospace business."
    ),
    "DHR": (
        "Danaher's history includes businesses separated into Veralto in 2023. "
        "The earlier operating scope differs from today's life-sciences and diagnostics portfolio."
    ),
    "WDC": (
        "Western Digital's pre-separation trading history reflects the former combined company. "
        "Adjusted prices may incorporate the Sandisk distribution, but the earlier operating scope "
        "is not identical to today's HDD-focused company."
    ),
}


class MarketDataError(RuntimeError):
    """Historical market data could not be loaded."""


def performance_context_note(ticker: str) -> str:
    return PERFORMANCE_NOTES.get(ticker, "")


def fetch_adjusted_monthly(symbol: str, *, years: int = 10, attempts: int = 5) -> pd.DataFrame:
    cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = int(cutoff.timestamp())
    start = end - int(years * 365.25 * 24 * 60 * 60)
    encoded = urllib.parse.quote(symbol, safe="")
    last_error: Exception | None = None
    payload: dict = {}
    for attempt in range(attempts):
        host = "query1.finance.yahoo.com" if attempt % 2 == 0 else "query2.finance.yahoo.com"
        url = (
            f"https://{host}/v8/finance/chart/{encoded}"
            f"?period1={start}&period2={end}&interval=1d&events=div%2Csplits&includeAdjustedClose=true"
        )
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = json.load(response)
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(min(2 ** attempt, 12))
    else:
        raise MarketDataError(f"Could not load historical prices for {symbol}.") from last_error
    result = payload.get("chart", {}).get("result", [])
    if not result:
        raise MarketDataError(f"No historical prices were returned for {symbol}.")
    block = result[0]
    return completed_monthly_closes(block, symbol, cutoff)


def completed_monthly_closes(block: dict, symbol: str, cutoff: datetime) -> pd.DataFrame:
    if str(block.get("meta", {}).get("symbol", "")).upper() != symbol:
        raise MarketDataError(f"Unexpected series returned for {symbol}.")
    adjusted = (block.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose") or []
    timestamps = block.get("timestamp") or []
    if len(adjusted) != len(timestamps) or not adjusted:
        raise MarketDataError(f"No adjusted close series for {symbol}.")
    frame = pd.DataFrame({"observation_date": pd.to_datetime(timestamps, unit="s", utc=True),
                          "adjusted_close": pd.to_numeric(adjusted, errors="coerce")}).dropna()
    frame = frame.loc[(frame.observation_date < cutoff) & (frame.adjusted_close > 0)
                      & frame.adjusted_close.map(math.isfinite)].sort_values("observation_date")
    if frame.empty or frame.observation_date.iloc[-1].date() < cutoff.date() - timedelta(days=6):
        raise MarketDataError(f"No recent completed trading session for {symbol}.")
    frame["date"] = frame.observation_date.dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    frame["observation_date"] = frame.observation_date.dt.strftime("%Y-%m-%d")
    result = frame.drop_duplicates("date", keep="last")
    if len(result) < 2:
        raise MarketDataError(f"Insufficient market history for {symbol}.")
    return result


def load_market_performance(ticker: str, path: Path = SNAPSHOT_PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["date", "series", "adjusted_close"])
    frame = pd.read_csv(path, parse_dates=["date"])
    requested = [ticker, *BENCHMARKS]
    selected = frame.loc[frame["series"].isin(requested)].copy()
    if selected.empty or ticker not in set(selected["series"]):
        return pd.DataFrame(columns=["date", "series", "adjusted_close"])
    if "observation_date" in selected:
        # A partially refreshed month must not compare Friday's stock close against Monday's ETF close.
        by_month = selected.groupby("date").observation_date
        valid_months = by_month.apply(lambda days: days.isna().all() or (days.notna().all() and days.nunique() == 1))
        selected = selected.loc[selected.date.isin(valid_months[valid_months].index)]
    pivot = selected.pivot_table(index="date", columns="series", values="adjusted_close", aggfunc="last").dropna()
    if pivot.empty:
        return pd.DataFrame(columns=["date", "series", "adjusted_close"])
    pivot = pivot.tail(121)
    rebased = pivot.div(pivot.iloc[0]).mul(100)
    labels = {ticker: ticker, "SPY": "SPY", "QQQ": "QQQ"}
    result = rebased.reset_index().melt(id_vars="date", var_name="series", value_name="growth_of_100")
    prices = pivot.reset_index().melt(id_vars="date", var_name="series", value_name="adjusted_close")
    result = result.merge(prices, on=["date", "series"], how="left", validate="one_to_one")
    if "observation_date" in selected:
        actual = selected.drop_duplicates("date").set_index("date").observation_date
        dates = pd.to_datetime(result.date.map(actual), errors="coerce")
        result["date"] = dates.fillna(result.date)
    result["series"] = result["series"].map(labels).fillna(result["series"])
    return result


def performance_summary(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame.empty:
        return []
    rows: list[dict[str, object]] = []
    dates = sorted(frame["date"].dropna().unique())
    years = max((pd.Timestamp(dates[-1]) - pd.Timestamp(dates[0])).days / 365.25, 1 / 12)
    for series, group in frame.groupby("series"):
        group = group.sort_values("date")
        ending = float(group.iloc[-1]["growth_of_100"])
        rows.append(
            {
                "series": series,
                "total_return": ending / 100 - 1,
                "annualized_return": (ending / 100) ** (1 / years) - 1,
                "years": years,
                "as_of": pd.Timestamp(group.iloc[-1]["date"]).date().isoformat(),
            }
        )
    return rows
