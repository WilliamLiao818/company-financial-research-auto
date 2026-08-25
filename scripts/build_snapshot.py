from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

import pandas as pd


COMPANIES = {
    "MSFT": {"cik": "0000789019", "company": "Microsoft Corporation"},
    "ORCL": {"cik": "0001341439", "company": "Oracle Corporation"},
    "NVDA": {"cik": "0001045810", "company": "NVIDIA Corporation"},
}

METRICS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "gross_profit": ["GrossProfit"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
}


def download_company_facts(cik: str) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if not user_agent or "@" not in user_agent:
        raise RuntimeError(
            "Set SEC_USER_AGENT to an identifiable name and public contact email before refreshing. "
            "The frozen demo does not require this setting."
        )
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def select_annual_facts(facts: dict, tags: list[str]) -> dict[str, dict]:
    """Return one latest-filed fact per annual period end, preferring tag order."""
    selected: dict[str, dict] = {}
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        units = us_gaap.get(tag, {}).get("units", {}).get("USD", [])
        candidates = [
            item
            for item in units
            if item.get("form") in {"10-K", "20-F", "40-F"}
            and item.get("fp") == "FY"
            and item.get("end")
        ]
        for item in candidates:
            period_end = item["end"]
            current = selected.get(period_end)
            if current is None or item.get("filed", "") > current.get("filed", ""):
                selected[period_end] = item
    return selected


def build_rows(ticker: str, config: dict, payload: dict, years: int = 5) -> list[dict]:
    metric_values = {name: select_annual_facts(payload, tags) for name, tags in METRICS.items()}
    available_periods = sorted(metric_values["revenue"])[-years:]
    source_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{config['cik']}.json"
    rows = []
    for period_end in available_periods:
        year = int(period_end[:4])
        row = {
            "ticker": ticker,
            "company": config["company"],
            "fiscal_year": year,
            "fiscal_year_end": period_end,
            "filed": "",
            "source_url": source_url,
        }
        for metric, values in metric_values.items():
            fact = values.get(period_end)
            row[metric] = fact.get("val") if fact else None
            if fact and metric == "revenue":
                row["filed"] = fact.get("filed", "")
        if row["gross_profit"] is None and row["revenue"] is not None and row["cost_of_revenue"] is not None:
            row["gross_profit"] = row["revenue"] - row["cost_of_revenue"]
        if row["liabilities"] is None and row["assets"] is not None and row["equity"] is not None:
            row["liabilities"] = row["assets"] - row["equity"]
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, help="Optional directory containing TICKER.json SEC snapshots")
    parser.add_argument("--output", type=Path, default=Path("data/financials.csv"))
    args = parser.parse_args()

    rows: list[dict] = []
    for ticker, config in COMPANIES.items():
        raw_path = args.raw_dir / f"{ticker}.json" if args.raw_dir else None
        if raw_path and raw_path.exists():
            payload = json.loads(raw_path.read_text())
        else:
            payload = download_company_facts(config["cik"])
        rows.extend(build_rows(ticker, config, payload))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output, index=False)
    print(f"Wrote {len(rows)} company-year rows to {args.output}")


if __name__ == "__main__":
    main()
