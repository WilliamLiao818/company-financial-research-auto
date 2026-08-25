import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research import financial_health_prompts, latest_company_summary, load_financials, quality_flags  # noqa: E402


def percent(value) -> str:
    return "—" if pd.isna(value) else f"{value:.1%}"


def main() -> None:
    data = load_financials()
    lines = [
        "# Company Financial Research Snapshot",
        "",
        "Public SEC XBRL facts, deterministic calculations and source links. Not investment advice.",
        "",
        "| Company | Fiscal year | Revenue | Growth | Gross margin | Operating margin | Free cash flow |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    checks: list[tuple[str, list[str], list[str]]] = []
    for ticker in sorted(data["ticker"].unique()):
        summary = latest_company_summary(data, ticker)
        lines.append(
            f"| [{summary['company']}]({summary['source_url']}) | {summary['fiscal_year']} | "
            f"${summary['revenue'] / 1e9:,.1f}B | {percent(summary['revenue_growth'])} | "
            f"{percent(summary['gross_margin'])} | {percent(summary['operating_margin'])} | "
            f"${summary['free_cash_flow'] / 1e9:,.1f}B |"
        )
        checks.append((ticker, financial_health_prompts(data, ticker), quality_flags(data, ticker)))
    for ticker, prompts, flags in checks:
        lines.extend(["", f"## {ticker} rule-based research prompts", ""])
        lines.extend(f"- {prompt}" for prompt in prompts)
        lines.extend(["", "Data-quality checks:", ""])
        lines.extend(f"- {flag}" for flag in flags)
    lines.extend(
        [
            "",
            "## Valuation boundary",
            "",
            "The interactive app includes a user-assumption scenario for growth, entry/exit multiples, net debt, MOIC and IRR. It is not a target price, DCF, investment recommendation or completed private-equity return model.",
        ]
    )
    output = ROOT / "output" / "company_brief.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
