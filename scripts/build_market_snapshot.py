from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_data import BENCHMARKS, fetch_adjusted_monthly  # noqa: E402
from research_catalog import COMPANY_NAMES  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=10, help="History window in years (1-20).")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "market_performance.csv")
    args = parser.parse_args()
    if not 1 <= args.years <= 20:
        parser.error("--years must be between 1 and 20")

    symbols = {**{ticker: ticker for ticker in COMPANY_NAMES}, **BENCHMARKS}
    frames = []
    for label, symbol in symbols.items():
        frame = fetch_adjusted_monthly(symbol, years=args.years)
        frame["series"] = label
        frames.append(frame)
        print(f"Loaded {label}: {len(frame)} monthly observations")
    output = pd.concat(frames, ignore_index=True)[["date", "series", "adjusted_close"]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(f"Wrote {len(output)} rows to {args.output}")


if __name__ == "__main__":
    main()
