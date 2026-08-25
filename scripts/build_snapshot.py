from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from input_pipeline import parse_identifiers  # noqa: E402
from sec_connector import company_facts_to_frame, fetch_company_facts  # noqa: E402


DEFAULT_IDENTIFIERS = ["MSFT", "ORCL", "NVDA"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--identifier",
        action="append",
        help="Ticker or CIK. Repeat the flag or provide a comma-separated value; defaults to the demo companies.",
    )
    parser.add_argument("--years", type=int, default=5, help="Latest annual periods to keep (1-20).")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        help="Optional directory containing IDENTIFIER.json SEC Company Facts snapshots; avoids online requests.",
    )
    parser.add_argument("--output", type=Path, default=Path("data/financials.csv"))
    args = parser.parse_args()
    if not 1 <= args.years <= 20:
        parser.error("--years must be between 1 and 20")

    identifier_text = ",".join(args.identifier or DEFAULT_IDENTIFIERS)
    identifiers = parse_identifiers(identifier_text)
    frames: list[pd.DataFrame] = []
    for identifier in identifiers:
        if args.raw_dir:
            raw_path = args.raw_dir / f"{identifier}.json"
            if not raw_path.exists():
                raise FileNotFoundError(f"No frozen SEC JSON input for {identifier}: {raw_path}")
            payload = json.loads(raw_path.read_text(encoding="utf-8"))
            ticker = identifier if not identifier.isdigit() and not identifier.startswith("CIK") else None
            frame = company_facts_to_frame(payload, ticker=ticker, years=args.years)
        else:
            frame = fetch_company_facts(identifier, years=args.years)
        frames.append(frame)

    output = pd.concat(frames, ignore_index=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(f"Wrote {len(output)} company-year rows to {args.output}")


if __name__ == "__main__":
    main()
