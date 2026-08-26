from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from company_profiles import accounting_quality_signals, fcf_bridge, profile_for
from input_pipeline import (
    company_facts_json_from_bytes,
    financial_csv_from_bytes,
    online_company_facts,
    parse_identifiers,
)
from pdf_export import markdown_to_pdf
from research import (
    DATA_PATH,
    VALUATION_METRICS,
    assumption_ledger,
    build_research_audit,
    build_run_manifest,
    evidence_ledger,
    filter_year_range,
    financial_health_prompts,
    formula_catalog,
    latest_company_summary,
    latest_peer_comparison,
    load_financials,
    manifest_json,
    quality_flags,
    render_research_report,
    review_queue,
    scenario_sensitivity,
    source_ledger,
    valuation_scenario,
)
from sec_connector import SecConfigurationError, SecConnectionError, SecInputError


st.set_page_config(page_title="The Company · Version 2.0", page_icon="C", layout="wide")
st.markdown(
    """
    <style>
    :root { --green:#087f5b; --ink:#10241c; --soft:#e8f5ef; --line:#dce7e1; }
    .stApp { background:#fbfdfc; color:var(--ink); }
    [data-testid="stHeader"] { background:rgba(251,253,252,.88); backdrop-filter:blur(16px); }
    [data-testid="stSidebar"] { background:#f1f7f4; border-right:1px solid var(--line); }
    h1,h2,h3 { letter-spacing:-.025em; }
    h1 { font-family:Georgia,serif!important; font-weight:400!important; }
    h2 { color:var(--ink); }
    div[data-testid="stMetric"] { padding:18px; background:white; border:1px solid var(--line); border-radius:16px; box-shadow:0 8px 24px rgba(16,36,28,.04); animation:rise .55s cubic-bezier(.22,1,.36,1) both; }
    div[data-testid="stMetricValue"] { color:var(--green); }
    .stButton>button,.stDownloadButton>button,.stLinkButton>a { border:0!important; border-radius:11px!important; color:white!important; background:var(--green)!important; font-weight:650!important; }
    .stButton>button:hover,.stDownloadButton>button:hover,.stLinkButton>a:hover { background:#065f46!important; transform:translateY(-1px); }
    div[data-baseweb="tab-list"] { gap:4px; border-bottom:1px solid var(--line); }
    button[data-baseweb="tab"] { padding:12px 16px; }
    button[data-baseweb="tab"][aria-selected="true"] { color:var(--green); }
    .thesis-card { min-height:170px; padding:22px; border:1px solid var(--line); border-radius:16px; background:white; }
    .thesis-card strong { display:block; margin-bottom:12px; color:var(--green); font-size:11px; letter-spacing:.12em; }
    .thesis-card p { margin:0; font-size:15px; line-height:1.65; }
    .scope-note { padding:15px 18px; border-left:3px solid var(--green); background:var(--soft); border-radius:0 12px 12px 0; color:#365448; font-size:13px; }
    @keyframes rise { from { transform:translateY(10px); opacity:0; } to { transform:none; opacity:1; } }
    @media (prefers-reduced-motion:reduce) { * { animation-duration:.01ms!important; transition-duration:.01ms!important; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def percent(value) -> str:
    return "—" if value is None or pd.isna(value) else f"{value:.1%}"


def usd_billions(value) -> str:
    return "—" if value is None or pd.isna(value) else f"${value / 1e9:,.1f}B"


def safe_file_name(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum() or character in "-_")


def enriched_report(
    frame: pd.DataFrame,
    ticker: str,
    peer_tickers: list[str],
    assumptions: dict[str, object],
    scenario: dict[str, object] | None,
    signals: pd.DataFrame,
) -> str:
    profile = profile_for(ticker)
    base = render_research_report(
        frame,
        primary_ticker=ticker,
        peer_tickers=peer_tickers,
        assumptions=assumptions,
        scenario=scenario,
    )
    sections = [
        f"# The Company: {ticker}",
        "",
        "> Fundamentals & Accounting Quality · Version 2.0. Public-source research support; not an investment recommendation.",
        "",
        "## Executive view",
        "",
        f"- **Business model:** {profile['business_model']}",
        f"- **Research thesis:** {profile['research_thesis']}",
        f"- **Counter-thesis:** {profile['counter_thesis']}",
        "",
        "## Business-model-specific indicators",
        "",
        *[f"- {item}" for item in profile["key_kpis"]],
        "",
        "## Priority diligence questions",
        "",
        *[f"- {item}" for item in profile["diligence_questions"]],
        "",
        "## Accounting quality and normalization",
        "",
    ]
    if signals.empty:
        sections.append("- No deterministic accounting-quality signal was triggered. This does not establish accounting quality.")
    else:
        sections.extend(
            [
                "| Signal | Category | Observation | Analytical implication | Required review | Confidence |",
                "|---|---|---|---|---|---|",
            ]
        )
        for row in signals.itertuples(index=False):
            sections.append(
                f"| {row.signal} | {row.category} | {row.observation} | {row.analytical_implication} | {row.required_review} | {row.confidence} |"
            )
    sections.extend(["", "---", "", base])
    return "\n".join(sections)


query_ticker = str(st.query_params.get("ticker", "MSFT")).upper()
showcase_tickers = ["MSFT", "ORCL"]
default_showcase = query_ticker if query_ticker in showcase_tickers else "MSFT"

st.sidebar.caption("THE COMPANY · VERSION 2.0")
mode = st.sidebar.radio(
    "Research mode",
    ["Prebuilt research pack", "Live SEC company · Beta", "Upload SEC Company Facts", "Upload financial CSV"],
    index=0 if query_ticker in showcase_tickers else 1,
)
current_year = date.today().year
start_year, end_year = current_year - 4, current_year

data: pd.DataFrame | None = None
try:
    if mode == "Prebuilt research pack":
        selected_showcase = st.sidebar.selectbox(
            "Company",
            showcase_tickers,
            index=showcase_tickers.index(default_showcase),
            format_func=lambda value: f"{value} · {'Microsoft' if value == 'MSFT' else 'Oracle'}",
        )
        data = load_financials()
        ticker_hint = selected_showcase
        st.sidebar.success("Verified snapshot · No API key required")
    elif mode == "Live SEC company · Beta":
        identifier = st.sidebar.text_input("U.S. ticker or CIK", value=query_ticker if query_ticker not in showcase_tickers else "AAPL")
        year_count = st.sidebar.slider("Annual periods", 3, 10, 5)
        st.sidebar.caption("The SEC connector does not require an API key. Availability depends on the public SEC endpoint and request identification.")
        if st.sidebar.button("Load SEC data", type="primary"):
            with st.spinner("Loading public SEC Company Facts…"):
                loaded = online_company_facts(parse_identifiers(identifier), years=year_count)
            st.session_state["live_company_data"] = loaded
            st.session_state["live_company_identifier"] = identifier
        if st.session_state.get("live_company_identifier") == identifier:
            data = st.session_state.get("live_company_data")
        if data is None:
            st.info("Enter a U.S. ticker and select **Load SEC data**. No figures are generated until the public filing data is returned.")
            st.stop()
        ticker_hint = str(data.iloc[0]["ticker"])
    elif mode == "Upload SEC Company Facts":
        uploaded = st.sidebar.file_uploader("Company Facts JSON", type=["json"])
        ticker_override = st.sidebar.text_input("Optional display ticker")
        st.sidebar.caption("The file is parsed in session memory and is not written by this application.")
        if uploaded is None:
            st.info("Upload a saved SEC Company Facts JSON file to continue.")
            st.stop()
        data = company_facts_json_from_bytes(uploaded.getvalue(), ticker=ticker_override.strip() or None, years=20)
        ticker_hint = str(data.iloc[0]["ticker"])
    else:
        uploaded = st.sidebar.file_uploader("Financial CSV", type=["csv"])
        st.sidebar.download_button("Download CSV template", DATA_PATH.read_bytes(), "financials-template.csv", "text/csv")
        st.sidebar.caption("The file is parsed in session memory and is not written by this application.")
        if uploaded is None:
            st.info("Upload a file matching the documented schema to continue.")
            st.stop()
        data = financial_csv_from_bytes(uploaded.getvalue())
        ticker_hint = str(data.iloc[0]["ticker"])

    available_years = pd.to_numeric(data["fiscal_year"], errors="coerce").dropna().astype(int)
    start_year = int(available_years.min())
    end_year = int(available_years.max())
    data = filter_year_range(data, start_year, end_year)
except (ValueError, SecInputError, SecConfigurationError, SecConnectionError) as error:
    st.error(str(error))
    st.caption("No substitute figures were generated. Use a prebuilt pack or provide a valid source file.")
    st.stop()

available_tickers = sorted(data["ticker"].unique())
ticker_index = available_tickers.index(ticker_hint) if ticker_hint in available_tickers else 0
ticker = st.sidebar.selectbox("Primary company", available_tickers, index=ticker_index)
peer_options = [item for item in available_tickers if item != ticker]
default_peers = peer_options if mode == "Prebuilt research pack" else []
peer_tickers = st.sidebar.multiselect("Comparison set", peer_options, default=default_peers)
scope_data = data.loc[data["ticker"].isin([ticker, *peer_tickers])].copy()
company = scope_data.loc[scope_data["ticker"] == ticker].sort_values("fiscal_year")
latest = company.iloc[-1]
summary = latest_company_summary(scope_data, ticker)
profile = profile_for(ticker)
signals = accounting_quality_signals(scope_data, ticker)

st.caption("THE COMPANY / FUNDAMENTALS & ACCOUNTING QUALITY")
st.title(f"{summary['company']}")
st.markdown(
    f"<div class='scope-note'><strong>{ticker}</strong> · FY{summary['fiscal_year']} · Public SEC facts · "
    "Facts, calculations, interpretations and assumptions remain separate.</div>",
    unsafe_allow_html=True,
)

metrics = st.columns(5)
metrics[0].metric("Revenue", usd_billions(summary["revenue"]), percent(summary["revenue_growth"]))
metrics[1].metric("Operating margin", percent(summary["operating_margin"]))
metrics[2].metric("Simple FCF", usd_billions(summary["free_cash_flow"]))
metrics[3].metric("Capex / revenue", percent(summary["capex_intensity"]))
metrics[4].metric("Cash conversion", "—" if pd.isna(summary["cash_conversion"]) else f"{summary['cash_conversion']:.2f}x")

executive_tab, financial_tab, accounting_tab, scenario_tab, evidence_tab = st.tabs(
    ["Executive View", "Financial Diagnostics", "Accounting Quality", "Valuation & Scenarios", "Evidence & PDF"]
)

with executive_tab:
    thesis_col, counter_col = st.columns(2)
    thesis_col.markdown(
        f"<div class='thesis-card'><strong>RESEARCH THESIS</strong><p>{profile['research_thesis']}</p></div>",
        unsafe_allow_html=True,
    )
    counter_col.markdown(
        f"<div class='thesis-card'><strong>COUNTER-THESIS</strong><p>{profile['counter_thesis']}</p></div>",
        unsafe_allow_html=True,
    )
    st.subheader("Business economics")
    st.write(profile["business_model"])
    left, right = st.columns(2)
    with left:
        st.markdown("**Growth engines**")
        for item in profile["growth_engines"]:
            st.write(f"- {item}")
        st.markdown("**Business-model-specific indicators**")
        for item in profile["key_kpis"]:
            st.write(f"- {item}")
    with right:
        st.markdown("**Priority diligence questions**")
        for item in profile["diligence_questions"]:
            st.write(f"- {item}")
    st.caption(f"Profile context: {profile['source_url']}")

with financial_tab:
    trend = company.melt(
        id_vars=["fiscal_year"],
        value_vars=["revenue", "operating_income", "net_income", "free_cash_flow"],
        var_name="metric",
        value_name="value",
    )
    trend["USD billions"] = trend["value"] / 1e9
    figure = px.line(
        trend,
        x="fiscal_year",
        y="USD billions",
        color="metric",
        markers=True,
        color_discrete_sequence=["#087f5b", "#35a77c", "#7bc5a5", "#173f32"],
    )
    figure.update_layout(
        title="Scale and cash generation are reviewed on the same fiscal-year basis",
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend_title_text="",
        transition_duration=550,
        margin={"l": 10, "r": 10, "t": 70, "b": 10},
    )
    figure.update_xaxes(dtick=1, gridcolor="#eef3f0")
    figure.update_yaxes(gridcolor="#eef3f0")
    st.plotly_chart(figure, width="stretch")

    display = company[
        ["fiscal_year", "revenue_growth", "operating_margin", "net_margin", "fcf_margin", "capex_intensity", "cash_conversion", "debt_to_assets_proxy"]
    ].copy()
    st.dataframe(
        display.style.format(
            {
                "revenue_growth": "{:.1%}",
                "operating_margin": "{:.1%}",
                "net_margin": "{:.1%}",
                "fcf_margin": "{:.1%}",
                "capex_intensity": "{:.1%}",
                "cash_conversion": "{:.2f}x",
                "debt_to_assets_proxy": "{:.1%}",
            },
            na_rep="—",
        ),
        hide_index=True,
        width="stretch",
    )
    left, right = st.columns(2)
    with left:
        st.subheader("Deterministic research prompts")
        for item in financial_health_prompts(scope_data, ticker):
            st.write(f"- {item}")
    with right:
        st.subheader("Data quality")
        for item in quality_flags(scope_data, ticker):
            st.write(f"- {item}")

    if peer_tickers:
        st.subheader("User-selected comparison")
        st.caption("Fiscal year ends and business models may differ. Selection does not establish strict comparability.")
        st.dataframe(latest_peer_comparison(scope_data), hide_index=True, width="stretch")

with accounting_tab:
    st.subheader("Accounting Quality & Normalization")
    st.caption("Signals identify review work. They do not allege misconduct and do not replace the original filing.")
    if signals.empty:
        st.success("No deterministic signal was triggered. This does not establish accounting quality.")
    else:
        st.dataframe(
            signals,
            column_config={"source_url": st.column_config.LinkColumn("Source")},
            hide_index=True,
            width="stretch",
        )

    bridge = fcf_bridge(scope_data, ticker)
    st.subheader("Reported-to-analytical cash-flow bridge")
    if len(bridge) > 1:
        waterfall = go.Figure(
            go.Waterfall(
                x=bridge["step"],
                y=bridge["amount_usd_billions"],
                measure=bridge["kind"],
                connector={"line": {"color": "#9db8ac"}},
                increasing={"marker": {"color": "#087f5b"}},
                decreasing={"marker": {"color": "#d97706"}},
                totals={"marker": {"color": "#173f32"}},
                text=[f"${value:,.1f}B" for value in bridge["amount_usd_billions"]],
                textposition="outside",
            )
        )
        waterfall.update_layout(
            title="An economic outflow can sit outside conventional CFO-minus-capex FCF",
            showlegend=False,
            plot_bgcolor="white",
            paper_bgcolor="white",
            transition_duration=550,
            margin={"l": 10, "r": 10, "t": 70, "b": 10},
        )
        waterfall.update_yaxes(title="USD billions", gridcolor="#eef3f0")
        st.plotly_chart(waterfall, width="stretch")
        st.info("The adjustment is an analytical view, not a restatement of reported cash flow. Confirm the lease note and use a consistent definition across periods and peers.")
    else:
        st.info("No sourced normalization adjustment is preloaded for this company. Reported simple FCF remains unchanged and any new adjustment requires source evidence.")

scenario = None
assumptions: dict[str, object] = {}
with scenario_tab:
    st.caption("Scenario outputs are transparent user assumptions—not market data, a target price or a recommendation.")
    available_metrics = [name for name in VALUATION_METRICS if name in latest.index and pd.notna(latest[name]) and latest[name] > 0]
    if not available_metrics:
        st.error("No positive base metric is available for the scenario model.")
    else:
        metric = st.selectbox("Base metric", available_metrics, format_func=lambda name: VALUATION_METRICS[name]["label"].split(" / ")[0])
        base_value = float(latest[metric] / 1e9)
        cols = st.columns(3)
        years = int(cols[0].number_input("Holding period · years", 1, 10, 5, 1))
        growth_rate = cols[1].number_input("Annual metric growth · %", -50.0, 100.0, 10.0, 1.0) / 100
        entry_multiple = cols[2].number_input("Entry multiple", min_value=.1, value=10.0, step=.5)
        cols = st.columns(3)
        exit_multiple = cols[0].number_input("Exit multiple", min_value=.1, value=10.0, step=.5)
        entry_net_debt = cols[1].number_input("Entry net debt · USD B", value=0.0, step=1.0)
        exit_net_debt = cols[2].number_input("Exit net debt · USD B", value=0.0, step=1.0)
        assumptions = {
            "valuation_metric": metric,
            "base_metric_usd_billions": base_value,
            "annual_growth_rate": growth_rate,
            "holding_period_years": years,
            "entry_multiple": entry_multiple,
            "exit_multiple": exit_multiple,
            "entry_net_debt_usd_billions": entry_net_debt,
            "exit_net_debt_usd_billions": exit_net_debt,
        }
        try:
            scenario = valuation_scenario(
                base_metric_value=base_value,
                metric=metric,
                annual_growth_rate=growth_rate,
                holding_period_years=years,
                entry_multiple=entry_multiple,
                exit_multiple=exit_multiple,
                entry_net_debt=entry_net_debt,
                exit_net_debt=exit_net_debt,
            )
        except ValueError as error:
            st.error(str(error))
        st.dataframe(assumption_ledger(assumptions), hide_index=True, width="stretch")
        if scenario:
            results = st.columns(4)
            results[0].metric("Entry equity value", f"${scenario['entry_equity_value']:,.1f}B")
            results[1].metric("Exit equity value", f"${scenario['exit_equity_value']:,.1f}B")
            results[2].metric("MOIC", f"{scenario['moic']:.2f}x")
            results[3].metric("IRR", f"{scenario['irr']:.1%}")
            sensitivity = scenario_sensitivity(
                base_metric_value=base_value,
                metric=metric,
                annual_growth_rates=[max(-.99, growth_rate - .05), growth_rate, growth_rate + .05],
                holding_period_years=years,
                entry_multiple=entry_multiple,
                exit_multiples=[max(.1, exit_multiple - 2), exit_multiple, exit_multiple + 2],
                entry_net_debt=entry_net_debt,
                exit_net_debt=exit_net_debt,
            )
            table = sensitivity.pivot(index="annual_growth_rate", columns="exit_multiple", values="irr")
            table.index = [f"{value:.1%}" for value in table.index]
            table.columns = [f"{value:.1f}x" for value in table.columns]
            st.subheader("IRR sensitivity · growth × exit multiple")
            st.dataframe(table.style.format("{:.1%}", na_rep="—"), width="stretch")

with evidence_tab:
    audit = build_research_audit(scope_data, assumptions=assumptions)
    queue = review_queue(scope_data)
    st.subheader("Evidence coverage and review queue")
    audit_metrics = st.columns(4)
    for column, (label, key) in zip(
        audit_metrics,
        [
            ("Core fact coverage", "core_fact_completeness"),
            ("Source metadata", "source_filing_metadata_coverage"),
            ("Fact provenance", "fact_provenance_coverage"),
        ],
    ):
        ratio = audit["metrics"][key]["ratio"]
        column.metric(label, "N/A" if ratio is None else f"{ratio:.1%}")
    audit_metrics[3].metric("Open review items", audit["review_queue_count"])
    if queue.empty:
        st.success("No item was generated under the published review rules.")
    else:
        st.dataframe(queue, hide_index=True, width="stretch")

    st.subheader("Source ledger")
    sources = source_ledger(scope_data)
    st.dataframe(sources, column_config={"source_url": st.column_config.LinkColumn("Public source")}, hide_index=True, width="stretch")
    facts = evidence_ledger(scope_data)

    report = enriched_report(scope_data, ticker, peer_tickers, assumptions, scenario, signals)
    report_pdf = markdown_to_pdf(report, document_title=f"The Company · {ticker}")
    manifest = build_run_manifest(
        scope_data,
        input_mode=mode,
        start_year=start_year,
        end_year=end_year,
        primary_ticker=ticker,
        peer_tickers=peer_tickers,
        assumptions=assumptions,
    )
    name = safe_file_name(ticker)
    downloads = st.columns(4)
    downloads[0].download_button("Download PDF report", report_pdf, f"{name}-company-report.pdf", "application/pdf", type="primary")
    downloads[1].download_button("Download Markdown", report, f"{name}-company-report.md", "text/markdown")
    downloads[2].download_button("Download fact ledger", facts.to_csv(index=False), f"{name}-reported-facts.csv", "text/csv")
    downloads[3].download_button("Download run record", manifest_json(manifest), f"{name}-run-manifest.json", "application/json")

    with st.expander("Formula catalog"):
        st.dataframe(formula_catalog(), hide_index=True, width="stretch")
    with st.expander("Report preview"):
        st.markdown(report)
    st.caption("Uploaded files are processed in session memory. Important conclusions should be checked against the original filing.")
