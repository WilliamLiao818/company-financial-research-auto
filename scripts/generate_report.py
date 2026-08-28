import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from company_profiles import accounting_quality_signals, fcf_bridge, profile_for  # noqa: E402
from pdf_export import build_company_pdf  # noqa: E402
from research import latest_company_summary, latest_peer_comparison, load_financials  # noqa: E402
from research_catalog import COMPANY_NAMES  # noqa: E402


def operating_scenarios(company: pd.DataFrame, profile: dict[str, object]) -> pd.DataFrame:
    latest = company.sort_values("fiscal_year").iloc[-1]
    defaults = profile["scenario_defaults"]
    years = int(defaults["years"])
    rows = []
    for case in ["bear", "base", "bull"]:
        growth = float(defaults[f"{case}_growth"])
        margin = float(defaults[f"{case}_margin"])
        revenue = float(latest["revenue"]) * (1 + growth) ** years
        rows.append(
            {
                "case": case.title(),
                "revenue": revenue,
                "operating_income": revenue * margin,
                "growth": growth,
                "margin": margin,
                "years": years,
            }
        )
    return pd.DataFrame(rows)


def generate_pdf(data: pd.DataFrame, ticker: str) -> bytes:
    company = data.loc[data["ticker"] == ticker].sort_values("fiscal_year")
    summary = latest_company_summary(data, ticker)
    profile = profile_for(ticker)
    return build_company_pdf(
        company,
        summary,
        profile,
        accounting_quality_signals(data, ticker),
        fcf_bridge(data, ticker),
        ticker=ticker,
        peers=latest_peer_comparison(data),
        scenarios=operating_scenarios(company, profile),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate chart-led company research PDFs.")
    parser.add_argument("tickers", nargs="*", help="Tickers to generate; defaults to every prebuilt company.")
    parser.add_argument("--output-dir", default=str(ROOT / "output" / "pdf"))
    arguments = parser.parse_args()

    data = load_financials()
    tickers = [ticker.upper() for ticker in arguments.tickers] or list(COMPANY_NAMES)
    unknown = [ticker for ticker in tickers if ticker not in COMPANY_NAMES]
    if unknown:
        parser.error("Unknown prebuilt ticker: " + ", ".join(unknown))

    output_dir = Path(arguments.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for ticker in tickers:
        destination = output_dir / f"{ticker.lower()}-company-report.pdf"
        destination.write_bytes(generate_pdf(data, ticker))
        print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
