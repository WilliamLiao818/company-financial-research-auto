from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from company_profiles import accounting_quality_signals, fcf_bridge, profile_for
from input_pipeline import company_facts_json_from_bytes, financial_csv_from_bytes, online_company_facts, parse_identifiers
from pdf_export import build_company_pdf
from research import (
    DATA_PATH,
    VALUATION_METRICS,
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
    review_queue,
    scenario_sensitivity,
    source_ledger,
    valuation_scenario,
)
from sec_connector import SecConfigurationError, SecConnectionError, SecInputError


SHOWCASES = {"MSFT": "Microsoft Corporation", "ORCL": "Oracle Corporation"}
MAX_UPLOAD_MB = 10

st.set_page_config(page_title="The Company · Version 2.0", page_icon="C", layout="wide", initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
    :root { --green:#087f5b; --dark:#10241c; --muted:#607068; --soft:#e8f5ef; --line:#dce7e1; }
    .stApp { background:#fbfdfc; color:var(--dark); }
    .block-container { max-width:1180px; padding-top:2.2rem; padding-bottom:4rem; }
    [data-testid="stHeader"] { background:rgba(251,253,252,.9); backdrop-filter:blur(18px); }
    h1 { font-family:Georgia,serif!important; font-weight:400!important; letter-spacing:-.045em!important; }
    h2,h3 { letter-spacing:-.025em!important; }
    div[data-testid="stMetric"] { padding:17px; background:white; border:1px solid var(--line); border-radius:16px; box-shadow:0 8px 24px rgba(16,36,28,.04); animation:rise .55s cubic-bezier(.22,1,.36,1) both; }
    div[data-testid="stMetricValue"] { color:var(--green); }
    .stButton>button,.stDownloadButton>button,.stLinkButton>a { min-height:44px; border:0!important; border-radius:12px!important; color:white!important; background:var(--green)!important; font-weight:700!important; transition:.2s ease; }
    .stButton>button:hover,.stDownloadButton>button:hover,.stLinkButton>a:hover { background:#065f46!important; transform:translateY(-1px); }
    div[data-baseweb="tab-list"] { gap:3px; border-bottom:1px solid var(--line); }
    button[data-baseweb="tab"] { padding:12px 14px; }
    button[data-baseweb="tab"][aria-selected="true"] { color:var(--green); }
    .hero-note { padding:16px 18px; border-left:3px solid var(--green); background:var(--soft); border-radius:0 13px 13px 0; color:#365448; font-size:13px; line-height:1.6; }
    .mode-card,.company-card,.story-card,.signal-card { height:100%; padding:22px; border:1px solid var(--line); border-radius:18px; background:white; box-shadow:0 10px 34px rgba(16,36,28,.035); }
    .mode-card strong,.company-card strong,.story-card strong,.signal-card strong { display:block; margin-bottom:10px; color:var(--green); font-size:11px; letter-spacing:.11em; }
    .mode-card h3,.company-card h3 { margin:.2rem 0 .65rem; }
    .mode-card p,.company-card p,.story-card p,.signal-card p { margin:0; color:var(--muted); font-size:14px; line-height:1.65; }
    .mode-card { min-height:210px; }
    .company-card { min-height:175px; }
    .story-card { min-height:190px; }
    .signal-card { min-height:220px; }
    .chart-shell { padding:12px 18px 2px; border:1px solid var(--line); border-radius:20px; background:white; }
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


def safe_name(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum() or character in "-_")


def base_pdf(frame: pd.DataFrame, ticker: str) -> bytes:
    company = frame.loc[frame["ticker"] == ticker].sort_values("fiscal_year")
    summary = latest_company_summary(frame, ticker)
    return build_company_pdf(company, summary, profile_for(ticker), accounting_quality_signals(frame, ticker), fcf_bridge(frame, ticker), ticker=ticker)


def choose(mode: str, ticker: str | None = None) -> None:
    st.session_state["active_mode"] = mode
    if ticker:
        st.session_state["selected_ticker"] = ticker
    st.rerun()


def render_landing() -> None:
    st.caption("THE COMPANY / FUNDAMENTALS & ACCOUNTING QUALITY · VERSION 2.0")
    st.title("Choose the company or evidence path first.")
    st.markdown(
        "<div class='hero-note'>Start with a complete public-source pack, load a U.S. public company from SEC Company Facts, or provide reviewed source files. Nothing is inferred when a required fact is missing.</div>",
        unsafe_allow_html=True,
    )
    st.subheader("Ready-to-use research packs")
    prebuilt = load_financials()
    columns = st.columns(2)
    for column, ticker in zip(columns, SHOWCASES):
        summary = latest_company_summary(prebuilt, ticker)
        with column:
            st.markdown(
                f"<div class='company-card'><strong>{ticker} · VERIFIED PUBLIC DATA</strong><h3>{SHOWCASES[ticker]}</h3><p>FY{summary['fiscal_year']} · Revenue {usd_billions(summary['revenue'])} · Operating margin {percent(summary['operating_margin'])}</p></div>",
                unsafe_allow_html=True,
            )
            actions = st.columns(2)
            if actions[0].button(f"Open {ticker}", key=f"open-{ticker}", width="stretch"):
                choose("prebuilt", ticker)
            actions[1].download_button("Download PDF", base_pdf(prebuilt, ticker), f"{ticker.lower()}-company-report.pdf", "application/pdf", key=f"landing-pdf-{ticker}", width="stretch")

    st.subheader("Four research modes")
    mode_specs = [
        ("01 · PREBUILT PACK", "MSFT or ORCL", "Complete reviewed dataset, accounting-quality diagnostics and PDF. No key or file required."),
        ("02 · LIVE SEC · BETA", "U.S. public company", "Enter a ticker or CIK. The system requests annual Company Facts from the public SEC endpoint; no commercial token is required."),
        ("03 · SEC JSON", "Saved Company Facts", "Upload one UTF-8 .json file, up to 10 MB. It must contain facts.us-gaap and annual USD facts. An optional ticker label may be supplied."),
        ("04 · FINANCIAL CSV", "Reviewed structured data", "Upload one UTF-8 .csv file, up to 10 MB. Dates use YYYY-MM-DD; financial fields are numeric or blank; source_url must use HTTP(S)."),
    ]
    columns = st.columns(4)
    for column, (label, title, description) in zip(columns, mode_specs):
        column.markdown(f"<div class='mode-card'><strong>{label}</strong><h3>{title}</h3><p>{description}</p></div>", unsafe_allow_html=True)

    with st.expander("Exact financial CSV schema"):
        st.code("ticker, company, fiscal_year, fiscal_year_end, filed, source_url, revenue, gross_profit, cost_of_revenue, operating_income, net_income, operating_cash_flow, capex, assets, liabilities, equity", language="text")
        st.markdown("One row per company and fiscal year. No duplicate company-year rows. Missing financial values stay blank; identifiers, dates and source URL are required.")
        st.download_button("Download CSV template", DATA_PATH.read_bytes(), "financials-template.csv", "text/csv")

    st.subheader("Use another source")
    selection = st.selectbox("Research mode", ["Live SEC company · Beta", "Upload SEC Company Facts JSON", "Upload financial CSV"], key="landing-custom-mode")
    if st.button("Continue", type="primary"):
        choose({"Live SEC company · Beta":"live", "Upload SEC Company Facts JSON":"json", "Upload financial CSV":"csv"}[selection])


raw_query_ticker = st.query_params.get("ticker")
query_ticker = str(raw_query_ticker).upper() if raw_query_ticker else ""
if "active_mode" not in st.session_state:
    if query_ticker in SHOWCASES:
        st.session_state["active_mode"] = "prebuilt"
        st.session_state["selected_ticker"] = query_ticker
    elif query_ticker:
        st.session_state["active_mode"] = "live"
        st.session_state["live_prefill"] = query_ticker
    else:
        st.session_state["active_mode"] = None

if st.session_state["active_mode"] is None:
    render_landing()
    st.stop()

top = st.columns([1.1, 4.5])
if top[0].button("← Choose input", width="stretch"):
    st.session_state["active_mode"] = None
    st.query_params.clear()
    st.rerun()
top[1].caption("THE COMPANY / FUNDAMENTALS & ACCOUNTING QUALITY · VERSION 2.0")

mode = st.session_state["active_mode"]
data: pd.DataFrame | None = None
ticker_hint = st.session_state.get("selected_ticker", "MSFT")
input_mode = mode
try:
    if mode == "prebuilt":
        selected = st.segmented_control("Company", list(SHOWCASES), default=ticker_hint if ticker_hint in SHOWCASES else "MSFT", format_func=lambda value: f"{value} · {SHOWCASES[value]}")
        ticker_hint = selected or "MSFT"
        st.session_state["selected_ticker"] = ticker_hint
        data = load_financials()
    elif mode == "live":
        st.subheader("Load public SEC Company Facts")
        st.caption("Enter a U.S. ticker or CIK. No commercial token is required; availability depends on the public SEC endpoint.")
        identifier = st.text_input("Ticker or CIK", value=st.session_state.get("live_prefill", "AAPL"))
        years = st.slider("Annual periods", 3, 10, 5)
        if st.button("Load company", type="primary"):
            with st.spinner("Loading public filing facts…"):
                st.session_state["live_data"] = online_company_facts(parse_identifiers(identifier), years=years)
                st.session_state["live_identifier"] = identifier
        if st.session_state.get("live_identifier") == identifier:
            data = st.session_state.get("live_data")
        if data is None:
            st.info("Load the ticker to begin. No substitute figures are generated while the source is unavailable.")
            st.stop()
        ticker_hint = str(data.iloc[0]["ticker"])
    elif mode == "json":
        st.subheader("Upload SEC Company Facts JSON")
        st.caption("UTF-8 .json, up to 10 MB. Required structure: facts.us-gaap with annual USD facts. The file is processed in session memory.")
        uploaded = st.file_uploader("Company Facts JSON", type=["json"])
        override = st.text_input("Optional display ticker")
        if uploaded is None:
            st.info("Select a valid Company Facts JSON file to begin.")
            st.stop()
        if uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise ValueError(f"The file exceeds {MAX_UPLOAD_MB} MB.")
        data = company_facts_json_from_bytes(uploaded.getvalue(), ticker=override.strip() or None, years=20)
        ticker_hint = str(data.iloc[0]["ticker"])
    else:
        st.subheader("Upload reviewed financial CSV")
        st.caption("UTF-8 .csv, up to 10 MB. Use the published schema; uploaded data is processed in session memory.")
        st.download_button("Download CSV template", DATA_PATH.read_bytes(), "financials-template.csv", "text/csv")
        uploaded = st.file_uploader("Financial CSV", type=["csv"])
        if uploaded is None:
            st.info("Select a CSV matching the published schema to begin.")
            st.stop()
        if uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise ValueError(f"The file exceeds {MAX_UPLOAD_MB} MB.")
        data = financial_csv_from_bytes(uploaded.getvalue())
        ticker_hint = str(data.iloc[0]["ticker"])
    years_available = pd.to_numeric(data["fiscal_year"], errors="coerce").dropna().astype(int)
    start_year, end_year = int(years_available.min()), int(years_available.max())
    data = filter_year_range(data, start_year, end_year)
except (ValueError, SecInputError, SecConfigurationError, SecConnectionError) as error:
    st.error(str(error))
    st.caption("No substitute figures were generated. Return to the input page or provide a valid source file.")
    st.stop()

available_tickers = sorted(data["ticker"].unique())
ticker = ticker_hint if ticker_hint in available_tickers else available_tickers[0]
peer_tickers = [value for value in available_tickers if value != ticker] if mode == "prebuilt" else []
scope = data.loc[data["ticker"].isin([ticker, *peer_tickers])].copy()
company = scope.loc[scope["ticker"] == ticker].sort_values("fiscal_year")
latest = company.iloc[-1]
summary = latest_company_summary(scope, ticker)
profile = profile_for(ticker)
signals = accounting_quality_signals(scope, ticker)
bridge = fcf_bridge(scope, ticker)
pdf_bytes = build_company_pdf(company, summary, profile, signals, bridge, ticker=ticker)

headline, download = st.columns([4.5, 1.5])
with headline:
    st.title(summary["company"])
    st.markdown(f"<div class='hero-note'><strong>{ticker}</strong> · FY{summary['fiscal_year']} · Public-source facts · The report separates facts, calculations, interpretations and assumptions.</div>", unsafe_allow_html=True)
with download:
    st.write("")
    st.write("")
    st.download_button("Download report · PDF", pdf_bytes, f"{safe_name(ticker)}-company-report.pdf", "application/pdf", type="primary", width="stretch")
    st.caption("Chart-led base report")

metrics = st.columns(5)
metrics[0].metric("Revenue", usd_billions(summary["revenue"]), percent(summary["revenue_growth"]))
metrics[1].metric("Operating margin", percent(summary["operating_margin"]))
metrics[2].metric("Simple FCF", usd_billions(summary["free_cash_flow"]))
metrics[3].metric("Capex / revenue", percent(summary["capex_intensity"]))
metrics[4].metric("Cash conversion", "—" if pd.isna(summary["cash_conversion"]) else f"{summary['cash_conversion']:.2f}x")

executive_tab, financial_tab, accounting_tab, scenario_tab, evidence_tab = st.tabs(["Executive answer", "Financial diagnostics", "Accounting quality", "Scenarios", "Evidence & downloads"])

with executive_tab:
    columns = st.columns(2)
    columns[0].markdown(f"<div class='story-card'><strong>THESIS</strong><p>{profile['research_thesis']}</p></div>", unsafe_allow_html=True)
    columns[1].markdown(f"<div class='story-card'><strong>COUNTER-THESIS</strong><p>{profile['counter_thesis']}</p></div>", unsafe_allow_html=True)
    st.subheader("Business economics")
    st.write(profile["business_model"])
    left, right = st.columns(2)
    with left:
        st.markdown("**Growth engines**")
        for item in profile["growth_engines"]:
            st.write(f"- {item}")
    with right:
        st.markdown("**Priority diligence**")
        for item in profile["diligence_questions"]:
            st.write(f"- {item}")

with financial_tab:
    trend = company.melt(id_vars=["fiscal_year"], value_vars=["revenue", "operating_income", "free_cash_flow"], var_name="metric", value_name="value")
    trend["USD billions"] = trend["value"] / 1e9
    figure = px.line(trend, x="fiscal_year", y="USD billions", color="metric", markers=True, color_discrete_sequence=["#087f5b", "#35a77c", "#173f32"])
    figure.update_layout(title="Scale and cash generation", height=390, plot_bgcolor="white", paper_bgcolor="white", legend_title_text="", margin={"l":20,"r":20,"t":65,"b":20}, transition_duration=550)
    figure.update_xaxes(dtick=1, gridcolor="#eef3f0")
    figure.update_yaxes(gridcolor="#eef3f0")
    _, center, _ = st.columns([.7, 6, .7])
    center.plotly_chart(figure, width="stretch")

    margin_data = company.melt(id_vars=["fiscal_year"], value_vars=["operating_margin", "net_margin", "fcf_margin", "capex_intensity"], var_name="metric", value_name="ratio")
    margin_data["Percent"] = margin_data["ratio"] * 100
    margin_figure = px.line(margin_data, x="fiscal_year", y="Percent", color="metric", markers=True, color_discrete_sequence=["#087f5b", "#173f32", "#76b89d", "#d97706"])
    margin_figure.update_layout(title="Margins and reinvestment intensity", height=360, plot_bgcolor="white", paper_bgcolor="white", legend_title_text="", margin={"l":20,"r":20,"t":65,"b":20}, transition_duration=550)
    margin_figure.update_xaxes(dtick=1, gridcolor="#eef3f0")
    margin_figure.update_yaxes(gridcolor="#eef3f0", ticksuffix="%")
    _, center, _ = st.columns([.7, 6, .7])
    center.plotly_chart(margin_figure, width="stretch")

    prompts, quality = st.columns(2)
    with prompts:
        st.subheader("What the trend asks next")
        for item in financial_health_prompts(scope, ticker):
            st.write(f"- {item}")
    with quality:
        st.subheader("Data quality")
        for item in quality_flags(scope, ticker):
            st.write(f"- {item}")

    if peer_tickers:
        st.subheader("MSFT / ORCL context")
        st.caption("A comparison is directional: fiscal-year ends and business models differ.")
        peers = latest_peer_comparison(scope)
        compare = [name for name in ["revenue_growth", "operating_margin", "net_margin", "fcf_margin"] if name in peers.columns]
        peer_chart = peers.melt(id_vars=["ticker"], value_vars=compare, var_name="metric", value_name="ratio")
        peer_chart["Percent"] = peer_chart["ratio"] * 100
        peer_figure = px.bar(peer_chart, x="metric", y="Percent", color="ticker", barmode="group", color_discrete_sequence=["#087f5b", "#76b89d"])
        peer_figure.update_layout(height=360, plot_bgcolor="white", paper_bgcolor="white", legend_title_text="", bargap=.28, margin={"l":20,"r":20,"t":25,"b":20})
        peer_figure.update_yaxes(gridcolor="#eef3f0", ticksuffix="%")
        _, center, _ = st.columns([.8, 5.5, .8])
        center.plotly_chart(peer_figure, width="stretch")

    with st.expander("Detailed financial data appendix"):
        st.dataframe(company, hide_index=True, width="stretch")

with accounting_tab:
    st.subheader("Noise filter: classification, timing and evidence gaps")
    st.caption("Signals identify review work. They do not allege misconduct and do not replace the original filing.")
    if signals.empty:
        st.success("No deterministic signal was triggered. This does not establish accounting quality.")
    else:
        for start in range(0, len(signals), 2):
            columns = st.columns(2)
            for column, row in zip(columns, signals.iloc[start:start + 2].itertuples(index=False)):
                column.markdown(f"<div class='signal-card'><strong>{row.category.upper()} · {row.confidence.upper()}</strong><h3>{row.signal}</h3><p>{row.observation}<br/><br/><b>Analytical implication:</b> {row.analytical_implication}<br/><br/><b>Required review:</b> {row.required_review}</p></div>", unsafe_allow_html=True)
    st.subheader("Reported-to-analytical cash-flow bridge")
    if len(bridge) > 1:
        waterfall = go.Figure(go.Waterfall(x=bridge["step"], y=bridge["amount_usd_billions"], measure=bridge["kind"], connector={"line":{"color":"#9db8ac"}}, increasing={"marker":{"color":"#087f5b"}}, decreasing={"marker":{"color":"#d97706"}}, totals={"marker":{"color":"#173f32"}}, text=[f"${value:,.1f}B" for value in bridge["amount_usd_billions"]], textposition="outside"))
        waterfall.update_layout(title="A reported classification can change the analytical view", height=380, showlegend=False, plot_bgcolor="white", paper_bgcolor="white", margin={"l":25,"r":25,"t":65,"b":30}, transition_duration=550)
        waterfall.update_yaxes(title="USD billions", gridcolor="#eef3f0")
        _, center, _ = st.columns([1.3, 5, 1.3])
        center.plotly_chart(waterfall, width="stretch")
        st.info("This adjustment is an analytical view, not a restatement. Confirm the lease note and keep definitions consistent across periods and peers.")
    else:
        st.info("No sourced normalization adjustment is preloaded. Any new adjustment requires source evidence.")

assumptions: dict[str, object] = {}
with scenario_tab:
    st.caption("Scenario outputs are transparent assumptions—not market data, a target price or a recommendation.")
    available_metrics = [name for name in VALUATION_METRICS if name in latest.index and pd.notna(latest[name]) and latest[name] > 0]
    if available_metrics:
        metric = st.selectbox("Base metric", available_metrics, format_func=lambda name: VALUATION_METRICS[name]["label"].split(" / ")[0])
        base_value = float(latest[metric] / 1e9)
        inputs = st.columns(4)
        years = int(inputs[0].number_input("Years", 1, 10, 5, 1))
        growth_rate = inputs[1].number_input("Annual growth · %", -50.0, 100.0, 10.0, 1.0) / 100
        entry_multiple = inputs[2].number_input("Entry multiple", min_value=.1, value=10.0, step=.5)
        exit_multiple = inputs[3].number_input("Exit multiple", min_value=.1, value=10.0, step=.5)
        assumptions = {"valuation_metric":metric,"base_metric_usd_billions":base_value,"annual_growth_rate":growth_rate,"holding_period_years":years,"entry_multiple":entry_multiple,"exit_multiple":exit_multiple,"entry_net_debt_usd_billions":0.0,"exit_net_debt_usd_billions":0.0}
        scenario = valuation_scenario(base_metric_value=base_value, metric=metric, annual_growth_rate=growth_rate, holding_period_years=years, entry_multiple=entry_multiple, exit_multiple=exit_multiple, entry_net_debt=0, exit_net_debt=0)
        results = st.columns(4)
        results[0].metric("Entry equity value", f"${scenario['entry_equity_value']:,.1f}B")
        results[1].metric("Exit equity value", f"${scenario['exit_equity_value']:,.1f}B")
        results[2].metric("MOIC", f"{scenario['moic']:.2f}x")
        results[3].metric("IRR", f"{scenario['irr']:.1%}")
        sensitivity = scenario_sensitivity(base_metric_value=base_value, metric=metric, annual_growth_rates=[max(-.99,growth_rate-.05),growth_rate,growth_rate+.05], holding_period_years=years, entry_multiple=entry_multiple, exit_multiples=[max(.1,exit_multiple-2),exit_multiple,exit_multiple+2], entry_net_debt=0, exit_net_debt=0)
        heat = sensitivity.pivot(index="annual_growth_rate", columns="exit_multiple", values="irr") * 100
        heat_figure = px.imshow(heat, text_auto=".1f", color_continuous_scale=[[0,"#e8f5ef"],[1,"#087f5b"]], labels={"x":"Exit multiple","y":"Annual growth","color":"IRR %"})
        heat_figure.update_layout(height=360, margin={"l":20,"r":20,"t":35,"b":20})
        _, center, _ = st.columns([1.4, 4.5, 1.4])
        center.plotly_chart(heat_figure, width="stretch")
    else:
        st.error("No positive base metric is available for the scenario model.")

with evidence_tab:
    audit = build_research_audit(scope, assumptions=assumptions)
    queue = review_queue(scope)
    st.subheader("Evidence coverage")
    coverage = pd.DataFrame({"Measure":["Core facts","Source metadata","Fact provenance"], "Percent":[100*(audit["metrics"]["core_fact_completeness"]["ratio"] or 0),100*(audit["metrics"]["source_filing_metadata_coverage"]["ratio"] or 0),100*(audit["metrics"]["fact_provenance_coverage"]["ratio"] or 0)]})
    coverage_figure = px.bar(coverage, x="Percent", y="Measure", orientation="h", color_discrete_sequence=["#087f5b"], text_auto=".0f")
    coverage_figure.update_layout(height=280, xaxis_range=[0,100], plot_bgcolor="white", paper_bgcolor="white", margin={"l":20,"r":20,"t":20,"b":20})
    coverage_figure.update_xaxes(ticksuffix="%", gridcolor="#eef3f0")
    _, center, _ = st.columns([1.2, 5, 1.2])
    center.plotly_chart(coverage_figure, width="stretch")
    st.markdown(f"**{audit['review_queue_count']} open review items.** The downloadable queue preserves exact source checks without overwhelming the main report.")
    if not queue.empty:
        for issue, count in queue["issue_type"].value_counts().head(4).items():
            st.write(f"- {count} × {str(issue).replace('_',' ')}")
    sources = source_ledger(scope)
    facts = evidence_ledger(scope)
    manifest = build_run_manifest(scope, input_mode=input_mode, start_year=start_year, end_year=end_year, primary_ticker=ticker, peer_tickers=peer_tickers, assumptions=assumptions)
    downloads = st.columns(4)
    downloads[0].download_button("PDF report", pdf_bytes, f"{safe_name(ticker)}-company-report.pdf", "application/pdf", type="primary", width="stretch")
    downloads[1].download_button("Reported facts", facts.to_csv(index=False), f"{safe_name(ticker)}-reported-facts.csv", "text/csv", width="stretch")
    downloads[2].download_button("Review queue", queue.to_csv(index=False), f"{safe_name(ticker)}-review-queue.csv", "text/csv", width="stretch")
    downloads[3].download_button("Run record", manifest_json(manifest), f"{safe_name(ticker)}-run-record.json", "application/json", width="stretch")
    with st.expander("Detailed source ledger"):
        st.dataframe(sources, column_config={"source_url":st.column_config.LinkColumn("Public source")}, hide_index=True, width="stretch")
    with st.expander("Formula catalog"):
        st.dataframe(formula_catalog(), hide_index=True, width="stretch")

st.caption("Public-source research support. Missing values remain missing. Outputs do not provide ratings, target prices or transaction instructions.")
