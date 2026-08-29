from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd


BENCHMARKS = {"SPY": "SPY", "QQQ": "QQQ"}
SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "market_performance.csv"


class MarketDataError(RuntimeError):
    """Historical market data could not be loaded."""


def fetch_adjusted_monthly(symbol: str, *, years: int = 10) -> pd.DataFrame:
    end = int(time.time())
    start = end - int(years * 365.25 * 24 * 60 * 60)
    encoded = urllib.parse.quote(symbol, safe="")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?period1={start}&period2={end}&interval=1mo&events=div%2Csplits&includeAdjustedClose=true"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise MarketDataError(f"Could not load historical prices for {symbol}.") from error
    result = payload.get("chart", {}).get("result", [])
    if not result:
        raise MarketDataError(f"No historical prices were returned for {symbol}.")
    block = result[0]
    timestamps = block.get("timestamp", [])
    adjusted = block.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])
    if not timestamps or not adjusted:
        adjusted = block.get("indicators", {}).get("quote", [{}])[0].get("close", [])
    frame = pd.DataFrame({"date": pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(None), "adjusted_close": adjusted})
    frame = frame.dropna().sort_values("date")
    frame["date"] = frame["date"].dt.to_period("M").dt.to_timestamp()
    return frame.drop_duplicates("date", keep="last")


def load_market_performance(ticker: str, path: Path = SNAPSHOT_PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["date", "series", "adjusted_close"])
    frame = pd.read_csv(path, parse_dates=["date"])
    requested = [ticker, *BENCHMARKS]
    selected = frame.loc[frame["series"].isin(requested)].copy()
    if selected.empty or ticker not in set(selected["series"]):
        return pd.DataFrame(columns=["date", "series", "adjusted_close"])
    pivot = selected.pivot_table(index="date", columns="series", values="adjusted_close", aggfunc="last").dropna()
    if pivot.empty:
        return pd.DataFrame(columns=["date", "series", "adjusted_close"])
    pivot = pivot.tail(121)
    rebased = pivot.div(pivot.iloc[0]).mul(100)
    labels = {ticker: ticker, "SPY": "SPY", "QQQ": "QQQ"}
    result = rebased.reset_index().melt(id_vars="date", var_name="series", value_name="growth_of_100")
    prices = pivot.reset_index().melt(id_vars="date", var_name="series", value_name="adjusted_close")
    result = result.merge(prices, on=["date", "series"], how="left", validate="one_to_one")
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
