from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
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
        time.sleep(0.25)
    output = pd.concat(frames, ignore_index=True)[["date", "series", "adjusted_close"]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{args.output.name}.", suffix=".tmp", dir=args.output.parent
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        output.to_csv(temporary_path, index=False)
        temporary_path.chmod(0o644)
        temporary_path.replace(args.output)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"Wrote {len(output)} rows to {args.output}")


if __name__ == "__main__":
    main()
