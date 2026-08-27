from __future__ import annotations

import pandas as pd

from research_catalog import EXTENDED_PROFILES


PROFILES = {
    "MSFT": {
        "business_model": "A diversified software, cloud and infrastructure platform monetized through subscriptions, consumption, licensing, advertising and devices.",
        "research_thesis": "Cloud and AI demand are expanding revenue and operating income, while the scale and classification of infrastructure investment are increasingly central to cash-flow quality.",
        "counter_thesis": "Infrastructure commitments may grow faster than monetization, increasing depreciation, lease obligations and the risk that headline cash generation overstates economic cash generation.",
        "growth_engines": ["Azure and cloud consumption", "Microsoft 365 commercial seat and ARPU expansion", "AI infrastructure and application monetization"],
        "key_kpis": ["Azure growth", "Commercial remaining performance obligations", "Capex intensity", "Finance lease additions and principal payments"],
        "key_questions": [
            "Can AI revenue scale quickly enough to earn an attractive return on the infrastructure build-out?",
            "How much of cloud demand is contracted, capacity-constrained or pulled forward?",
            "Does the current operating-margin profile survive a higher depreciation and energy-cost base?",
        ],
        "moat_factors": [
            ("Enterprise distribution", "A broad installed base gives the company multiple routes to deploy new cloud and AI products."),
            ("Integrated stack", "Infrastructure, data, productivity and developer tools reinforce cross-product adoption."),
            ("Switching costs", "Identity, workflow, data and application dependencies can make platform changes operationally expensive."),
            ("Capital scale", "Large investment capacity supports global infrastructure, but raises the hurdle for cash returns."),
        ],
        "catalysts": [
            "Azure and AI revenue growth sustains while capacity constraints ease.",
            "Commercial backlog converts into revenue without a comparable step-up in customer-acquisition cost.",
            "New application-layer AI revenue improves the return profile of infrastructure investment.",
            "Capex growth moderates before revenue and operating-profit momentum fades.",
        ],
        "risks": [
            "Infrastructure investment and lease commitments outrun monetization.",
            "Depreciation, power and data-center costs compress incremental margins.",
            "Cloud customers optimize workloads or shift to competing and custom architectures.",
            "Regulatory remedies constrain bundling, distribution or acquisition strategy.",
        ],
        "monitoring_signals": [
            ("Demand", "Azure growth, contracted backlog and capacity commentary"),
            ("Returns", "Incremental operating profit versus capex and lease additions"),
            ("Cash", "Reported FCF, finance-lease principal and working-capital timing"),
            ("Competition", "Workload wins, pricing, custom silicon and model distribution"),
        ],
        "scenario_defaults": {
            "years": 3,
            "bear_growth": 0.08,
            "base_growth": 0.13,
            "bull_growth": 0.18,
            "bear_margin": 0.42,
            "base_margin": 0.46,
            "bull_margin": 0.49,
        },
        "competitive_dimensions": ["Cloud scale", "Enterprise distribution", "Data depth", "Application reach", "AI ecosystem"],
        "competitive_scores": {
            "Microsoft": [5, 5, 4, 5, 5],
            "AWS": [5, 4, 3, 3, 5],
            "Google": [4, 3, 4, 4, 5],
            "Oracle": [3, 5, 5, 4, 3],
        },
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
        "key_questions": [
            "Can contracted cloud demand convert quickly enough to absorb the current capacity build-out?",
            "Will Oracle preserve database economics as infrastructure becomes a larger share of the mix?",
            "How much financial flexibility remains if capex stays elevated and deployment timing slips?",
        ],
        "moat_factors": [
            ("Database estate", "Mission-critical database workloads and embedded operational processes support durable switching costs."),
            ("Enterprise relationships", "A large installed base creates distribution for cloud infrastructure and applications."),
            ("Integrated data stack", "Database, infrastructure and applications can reduce integration complexity for selected workloads."),
            ("Contracted demand", "A large backlog can improve visibility, but conversion timing and capacity requirements remain decisive."),
        ],
        "catalysts": [
            "Cloud backlog converts to revenue faster than infrastructure costs mature.",
            "Database and application customers expand onto Oracle Cloud Infrastructure.",
            "Capex intensity peaks while cloud growth and operating cash flow remain resilient.",
            "New capacity improves utilization without requiring materially weaker pricing.",
        ],
        "risks": [
            "Capex and commitments remain elevated for longer than cash generation can support.",
            "Customer deployments are delayed or concentrated among a small number of counterparties.",
            "Hyperscale competitors use broader ecosystems, custom silicon or price to pressure returns.",
            "Leverage and refinancing needs reduce flexibility during a slower demand environment.",
        ],
        "monitoring_signals": [
            ("Demand", "Cloud growth, backlog conversion and customer deployment timing"),
            ("Returns", "Incremental cloud profit versus capex and depreciation"),
            ("Cash", "Operating cash flow, simple FCF and commitment disclosures"),
            ("Balance sheet", "Liability growth, liquidity and financing requirements"),
        ],
        "scenario_defaults": {
            "years": 3,
            "bear_growth": 0.09,
            "base_growth": 0.15,
            "bull_growth": 0.21,
            "bear_margin": 0.27,
            "base_margin": 0.31,
            "bull_margin": 0.35,
        },
        "competitive_dimensions": ["Cloud scale", "Enterprise distribution", "Data depth", "Application reach", "AI ecosystem"],
        "competitive_scores": {
            "Oracle": [3, 5, 5, 4, 3],
            "Microsoft": [5, 5, 4, 5, 5],
            "AWS": [5, 4, 3, 3, 5],
            "Google": [4, 3, 4, 4, 5],
            "SAP": [2, 5, 4, 5, 3],
        },
        "diligence_questions": [
            "What utilization and pricing assumptions support the current infrastructure build-out?",
            "How much contracted demand is cancellable, capacity-constrained or dependent on customer deployment timing?",
            "What is the expected path from capital expenditure to normalized free cash flow?",
        ],
        "source_url": "https://www.sec.gov/Archives/edgar/data/1341439/000095017026090794/orcl-20260531.htm",
    },
}

PROFILES.update(EXTENDED_PROFILES)


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
            "key_questions": ["Which company-specific evidence would change the current view?"],
            "moat_factors": [("Unscored", "A company-specific competitive review is required.")],
            "catalysts": ["No reviewed catalyst set is available."],
            "risks": ["No reviewed risk set is available."],
            "monitoring_signals": [("Evidence", "Add company-specific operating indicators")],
            "scenario_defaults": {"years": 3, "bear_growth": 0.0, "base_growth": 0.05, "bull_growth": 0.1, "bear_margin": 0.1, "base_margin": 0.15, "bull_margin": 0.2},
            "competitive_dimensions": ["Evidence coverage"],
            "competitive_scores": {str(ticker): [1]},
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
