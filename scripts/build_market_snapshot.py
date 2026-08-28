from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_data import BENCHMARKS, fetch_adjusted_monthly  # noqa: E402
from research_catalog import COMPANY_NAMES  # noqa: E402


def main() -> None:
    symbols = {**{ticker: ticker for ticker in COMPANY_NAMES}, **BENCHMARKS}
    frames = []
    for label, symbol in symbols.items():
        frame = fetch_adjusted_monthly(symbol, years=10)
        frame["series"] = label
        frames.append(frame)
        print(f"Loaded {label}: {len(frame)} monthly observations")
    output = pd.concat(frames, ignore_index=True)[["date", "series", "adjusted_close"]]
    path = ROOT / "data" / "market_performance.csv"
    output.to_csv(path, index=False)
    print(f"Wrote {len(output)} rows to {path}")


if __name__ == "__main__":
    main()
