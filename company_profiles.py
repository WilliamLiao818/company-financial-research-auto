from __future__ import annotations

import pandas as pd


PROFILES = {
    "MSFT": {
        "business_model": "A diversified software, cloud and infrastructure platform monetized through subscriptions, consumption, licensing, advertising and devices.",
        "research_thesis": "Cloud and AI demand are expanding revenue and operating income, while the scale and classification of infrastructure investment are increasingly central to cash-flow quality.",
        "counter_thesis": "Infrastructure commitments may grow faster than monetization, increasing depreciation, lease obligations and the risk that headline cash generation overstates economic cash generation.",
        "growth_engines": ["Azure and cloud consumption", "Microsoft 365 commercial seat and ARPU expansion", "AI infrastructure and application monetization"],
        "key_kpis": ["Azure growth", "Commercial remaining performance obligations", "Capex intensity", "Finance lease additions and principal payments"],
        "diligence_questions": [
            "How much incremental AI infrastructure demand is contracted versus capacity built ahead of demand?",
            "What portion of infrastructure spending is owned capex versus finance or operating leases?",
            "How quickly does incremental infrastructure convert into revenue, operating profit and cash returns?",
        ],
        "source_url": "https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm",
    },
    "ORCL": {
        "business_model": "A database, enterprise software and cloud infrastructure platform monetized through cloud services, license support, cloud licenses and hardware.",
        "research_thesis": "Cloud infrastructure and contracted demand are accelerating growth, but the investment case increasingly depends on converting a sharp capital-spending step-up into durable cash returns.",
        "counter_thesis": "High infrastructure investment, debt and long-dated commitments can pressure free cash flow if cloud utilization or customer deployment timing trails capacity additions.",
        "growth_engines": ["Oracle Cloud Infrastructure", "Database and application cloud services", "Contracted cloud demand conversion"],
        "key_kpis": ["Cloud services growth", "Remaining performance obligations", "Capex intensity", "Operating cash conversion and leverage"],
        "diligence_questions": [
            "What utilization and pricing assumptions support the current infrastructure build-out?",
            "How much contracted demand is cancellable, capacity-constrained or dependent on customer deployment timing?",
            "What is the expected path from capital expenditure to normalized free cash flow?",
        ],
        "source_url": "https://www.sec.gov/Archives/edgar/data/1341439/000095017026090794/orcl-20260531.htm",
    },
}


MSFT_FINANCE_LEASE_PRINCIPAL = {
    2024: 1.286e9,
    2025: 2.283e9,
    2026: 3.101e9,
}


def profile_for(ticker: str) -> dict[str, object]:
    return PROFILES.get(
        ticker,
        {
            "business_model": "No prebuilt business-model profile is available for this identifier.",
            "research_thesis": "Use reported financial trends as a starting point and verify the business drivers in the original filings.",
            "counter_thesis": "A standardized SEC fact set cannot by itself establish competitive position, unit economics or sustainable value creation.",
            "growth_engines": ["Review company-specific segment disclosures"],
            "key_kpis": ["Select business-model-specific operating indicators"],
            "diligence_questions": ["Which company-specific disclosures are required before forming a view?"],
            "source_url": "https://www.sec.gov/edgar/search/",
        },
    )


def accounting_quality_signals(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    company = frame.loc[frame["ticker"] == ticker].sort_values("fiscal_year")
    if company.empty:
        return pd.DataFrame()
    latest = company.iloc[-1]
    prior = company.iloc[-2] if len(company) > 1 else None
    rows: list[dict[str, object]] = []

    def add(signal: str, category: str, observation: str, implication: str, review: str, confidence: str, source_url: str) -> None:
        rows.append(
            {
                "signal": signal,
                "category": category,
                "observation": observation,
                "analytical_implication": implication,
                "required_review": review,
                "confidence": confidence,
                "source_url": source_url,
            }
        )

    source = str(latest.get("source_url", ""))
    if prior is not None and pd.notna(latest.get("capex")) and pd.notna(prior.get("capex")) and float(prior["capex"]) > 0:
        change = float(latest["capex"] / prior["capex"] - 1)
        if change >= .25:
            add(
                "Capital expenditure step-up",
                "Economic cash flow",
                f"Reported capex increased {change:.1%} year over year.",
                "Simple FCF is absorbing a larger investment cycle; maintenance and growth capex should not be assumed equivalent.",
                "Reconcile the increase to data centers, equipment, construction commitments and management capacity commentary.",
                "High",
                source,
            )

    if pd.notna(latest.get("cash_conversion")):
        conversion = float(latest["cash_conversion"])
        if conversion >= 1.25 or conversion < .8:
            add(
                "Cash conversion divergence",
                "Timing and non-cash items",
                f"Operating cash flow / net income is {conversion:.2f}x.",
                "The difference may reflect working capital, deferred revenue, stock compensation, taxes or other non-cash items rather than steady-state economics.",
                "Build an operating-cash-flow bridge from the filing before treating the ratio as persistent.",
                "Medium",
                source,
            )

    missing = [field for field in ["gross_profit", "cost_of_revenue"] if field not in latest.index or pd.isna(latest[field])]
    if missing:
        add(
            "Standardized fact gap",
            "Evidence coverage",
            "The SEC Company Facts snapshot does not provide: " + ", ".join(missing) + ".",
            "Gross-margin conclusions should remain unavailable instead of being inferred from another label or period.",
            "Read the primary statements and company-specific XBRL tags; retain null values until verified.",
            "High",
            source,
        )

    if ticker == "MSFT" and int(latest["fiscal_year"]) in MSFT_FINANCE_LEASE_PRINCIPAL:
        principal = MSFT_FINANCE_LEASE_PRINCIPAL[int(latest["fiscal_year"])]
        add(
            "Finance lease principal outside operating cash flow",
            "Cash-flow classification",
            f"The filing reports ${principal / 1e9:.1f}B of finance lease principal in financing cash flow for FY{int(latest['fiscal_year'])}.",
            "Conventional CFO-minus-capex FCF excludes this economic cash outflow, so an analyst may subtract it for an infrastructure-adjusted view.",
            "Confirm the lease note, avoid describing classification as manipulation, and compare like-for-like definitions across periods.",
            "High",
            PROFILES["MSFT"]["source_url"],
        )

    return pd.DataFrame(rows)


def fcf_bridge(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    company = frame.loc[frame["ticker"] == ticker].sort_values("fiscal_year")
    if company.empty:
        return pd.DataFrame(columns=["step", "amount_usd_billions", "kind"])
    latest = company.iloc[-1]
    fiscal_year = int(latest["fiscal_year"])
    reported_fcf = float(latest["free_cash_flow"] / 1e9)
    rows = [{"step": "Reported simple FCF", "amount_usd_billions": reported_fcf, "kind": "absolute"}]
    lease_principal = MSFT_FINANCE_LEASE_PRINCIPAL.get(fiscal_year) if ticker == "MSFT" else None
    if lease_principal:
        rows.extend(
            [
                {"step": "Finance lease principal", "amount_usd_billions": -lease_principal / 1e9, "kind": "relative"},
                {"step": "Infrastructure-adjusted FCF", "amount_usd_billions": reported_fcf - lease_principal / 1e9, "kind": "total"},
            ]
        )
    return pd.DataFrame(rows)
