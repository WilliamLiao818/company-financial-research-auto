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
    :root { --green:#087f5b; --dark:#10241c; --muted:#4f645a; --soft:#e8f5ef; --line:#d3e1da; }
    .stApp { background:#fbfdfc; color:var(--dark); }
    .block-container { max-width:1180px; padding-top:2.2rem; padding-bottom:4rem; }
    [data-testid="stHeader"] { background:rgba(251,253,252,.9); backdrop-filter:blur(18px); }
    [data-testid="stAppViewContainer"] p,
    [data-testid="stAppViewContainer"] label,
    [data-testid="stAppViewContainer"] li,
    [data-testid="stAppViewContainer"] span { color:var(--dark); }
    [data-testid="stCaptionContainer"] p { color:var(--muted)!important; }
    h1 { font-family:Georgia,serif!important; font-weight:400!important; letter-spacing:-.045em!important; }
    h2,h3 { letter-spacing:-.025em!important; }
    div[data-testid="stMetric"] { padding:17px; background:white; border:1px solid var(--line); border-radius:16px; box-shadow:0 8px 24px rgba(16,36,28,.04); animation:rise .55s cubic-bezier(.22,1,.36,1) both; }
    div[data-testid="stMetricValue"] { color:var(--green); }
    .stButton>button,.stDownloadButton>button,.stLinkButton>a { min-height:44px; border:0!important; border-radius:12px!important; color:white!important; background:var(--green)!important; font-weight:700!important; transition:.2s ease; }
    .stButton>button:hover,.stDownloadButton>button:hover,.stLinkButton>a:hover { background:#065f46!important; transform:translateY(-1px); }
    div[data-baseweb="tab-list"] { gap:3px; border-bottom:1px solid var(--line); }
    button[data-baseweb="tab"] { padding:12px 13px; color:#52665c!important; }
    button[data-baseweb="tab"] p { color:inherit!important; font-weight:650!important; }
    button[data-baseweb="tab"][aria-selected="true"] { color:var(--green)!important; }
    .stButton>button p,.stDownloadButton>button p,.stLinkButton>a p { color:white!important; }
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
    .section-deck { max-width:760px; color:var(--muted); line-height:1.65; margin-bottom:1.1rem; }
    .research-strip { padding:14px 18px; border:1px solid var(--line); border-radius:14px; background:white; color:var(--dark); font-size:13px; line-height:1.65; }
    .research-strip b { color:var(--green); }
    .compact-card { min-height:150px; padding:18px; border:1px solid var(--line); border-radius:16px; background:white; }
    .compact-card strong { display:block; color:var(--green); font-size:11px; letter-spacing:.1em; margin-bottom:8px; }
    .compact-card p { color:var(--muted)!important; font-size:13px; line-height:1.6; margin:0; }
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


def style_figure(figure: go.Figure, *, title: str | None = None, height: int = 360, legend: str = "h") -> go.Figure:
    """Apply one readable institutional chart system across every page."""
    figure.update_layout(
        title={"text": title, "font": {"size": 18, "color": "#10241c"}, "x": 0.02} if title else None,
        height=height,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font={"family": "Arial, sans-serif", "size": 12, "color": "#263d33"},
        legend={"title": {"text": ""}, "orientation": legend, "yanchor": "bottom", "y": 1.02, "x": 0.02},
        hoverlabel={"bgcolor": "#10241c", "font": {"color": "white"}},
        margin={"l": 58, "r": 28, "t": 72 if title else 42, "b": 54},
        transition_duration=500,
    )
    figure.update_xaxes(showline=True, linecolor="#c9d8d0", gridcolor="#edf3f0", tickfont={"color": "#3d5148"}, title_font={"color": "#263d33"}, zerolinecolor="#c9d8d0")
    figure.update_yaxes(showline=False, gridcolor="#e6efea", tickfont={"color": "#3d5148"}, title_font={"color": "#263d33"}, zerolinecolor="#c9d8d0")
    return figure


def operating_scenarios(company: pd.DataFrame, profile: dict[str, object]) -> pd.DataFrame:
    latest = company.sort_values("fiscal_year").iloc[-1]
    defaults = profile["scenario_defaults"]
    years = int(defaults["years"])
    rows = []
    for case in ["bear", "base", "bull"]:
        growth = float(defaults[f"{case}_growth"])
        margin = float(defaults[f"{case}_margin"])
        revenue = float(latest["revenue"]) * (1 + growth) ** years
        rows.append({"case": case.title(), "revenue": revenue, "operating_income": revenue * margin, "growth": growth, "margin": margin, "years": years})
    return pd.DataFrame(rows)


def competitive_frame(profile: dict[str, object]) -> pd.DataFrame:
    rows = []
    for name, scores in profile["competitive_scores"].items():
        for dimension, score in zip(profile["competitive_dimensions"], scores):
            rows.append({"company": name, "dimension": dimension, "score": score})
    return pd.DataFrame(rows)


def base_pdf(frame: pd.DataFrame, ticker: str) -> bytes:
    company = frame.loc[frame["ticker"] == ticker].sort_values("fiscal_year")
    summary = latest_company_summary(frame, ticker)
    profile = profile_for(ticker)
    return build_company_pdf(
        company,
        summary,
        profile,
        accounting_quality_signals(frame, ticker),
        fcf_bridge(frame, ticker),
        ticker=ticker,
        peers=latest_peer_comparison(frame),
        scenarios=operating_scenarios(company, profile),
    )


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
peer_summary = latest_peer_comparison(scope)
scenario_frame = operating_scenarios(company, profile)
pdf_bytes = build_company_pdf(company, summary, profile, signals, bridge, ticker=ticker, peers=peer_summary, scenarios=scenario_frame)

headline, download = st.columns([4.5, 1.5])
with headline:
    st.title(summary["company"])
    st.markdown(f"<div class='hero-note'><strong>{ticker}</strong> · FY{summary['fiscal_year']} · Public-source facts · The report separates facts, calculations, interpretations and assumptions.</div>", unsafe_allow_html=True)
with download:
    st.write("")
    st.write("")
    st.download_button("Download report · PDF", pdf_bytes, f"{safe_name(ticker)}-company-report.pdf", "application/pdf", type="primary", width="stretch")
    st.caption("Full institutional-style research report")

metrics = st.columns(5)
metrics[0].metric("Revenue", usd_billions(summary["revenue"]), percent(summary["revenue_growth"]))
metrics[1].metric("Operating margin", percent(summary["operating_margin"]))
metrics[2].metric("Simple FCF", usd_billions(summary["free_cash_flow"]))
metrics[3].metric("Capex / revenue", percent(summary["capex_intensity"]))
metrics[4].metric("Cash conversion", "—" if pd.isna(summary["cash_conversion"]) else f"{summary['cash_conversion']:.2f}x")

executive_tab, business_tab, earnings_tab, cash_tab, peer_tab, scenario_tab, risk_tab, evidence_tab = st.tabs([
    "Executive view",
    "Business & moat",
    "Earnings",
    "Cash & quality",
    "Peers",
    "Scenario lab",
    "Catalysts & risks",
    "Evidence",
])

with executive_tab:
    st.subheader("Answer first")
    st.markdown("<div class='section-deck'>A decision-ready opening: what matters, what could invalidate it, and which questions the evidence must answer next.</div>", unsafe_allow_html=True)
    columns = st.columns(2)
    columns[0].markdown(f"<div class='story-card'><strong>THESIS</strong><p>{profile['research_thesis']}</p></div>", unsafe_allow_html=True)
    columns[1].markdown(f"<div class='story-card'><strong>COUNTER-THESIS</strong><p>{profile['counter_thesis']}</p></div>", unsafe_allow_html=True)
    st.subheader("Pivotal questions")
    questions = st.columns(3)
    for index, (column, question) in enumerate(zip(questions, profile["key_questions"]), start=1):
        column.markdown(f"<div class='compact-card'><strong>QUESTION {index:02d}</strong><p>{question}</p></div>", unsafe_allow_html=True)
    st.subheader("Latest read-through")
    st.markdown(
        f"<div class='research-strip'><b>Growth:</b> revenue changed {percent(summary['revenue_growth'])} year over year. "
        f"<b>Profitability:</b> operating margin is {percent(summary['operating_margin'])}. "
        f"<b>Reinvestment:</b> capex is {percent(summary['capex_intensity'])} of revenue. "
        f"<b>Cash:</b> simple FCF is {usd_billions(summary['free_cash_flow'])}. These indicators frame the next research questions; they do not establish a rating.</div>",
        unsafe_allow_html=True,
    )

with business_tab:
    st.subheader("Business model and competitive durability")
    st.markdown(f"<div class='hero-note'>{profile['business_model']}</div>", unsafe_allow_html=True)
    st.markdown("### Growth engines")
    engines = st.columns(len(profile["growth_engines"]))
    for index, (column, item) in enumerate(zip(engines, profile["growth_engines"]), start=1):
        column.markdown(f"<div class='compact-card'><strong>ENGINE {index:02d}</strong><p>{item}</p></div>", unsafe_allow_html=True)
    st.markdown("### Moat assessment")
    for start in range(0, len(profile["moat_factors"]), 2):
        columns = st.columns(2)
        for column, (label, explanation) in zip(columns, profile["moat_factors"][start:start + 2]):
            column.markdown(f"<div class='compact-card'><strong>{label.upper()}</strong><p>{explanation}</p></div>", unsafe_allow_html=True)
    st.markdown("### Operating indicators to monitor")
    st.write(" · ".join(profile["key_kpis"]))

with earnings_tab:
    st.subheader("Earnings power and operating trajectory")
    st.markdown("<div class='section-deck'>Historical statements are decomposed into scale, growth, margins and reinvestment so the underlying operating direction is visible before judgment is applied.</div>", unsafe_allow_html=True)
    trend = company.melt(id_vars=["fiscal_year"], value_vars=["revenue", "operating_income", "free_cash_flow"], var_name="metric", value_name="value")
    trend["USD billions"] = trend["value"] / 1e9
    figure = px.line(trend, x="fiscal_year", y="USD billions", color="metric", markers=True, color_discrete_sequence=["#087f5b", "#35a77c", "#173f32"])
    style_figure(figure, title="Scale and cash generation · USD billions", height=390)
    figure.update_xaxes(dtick=1, title="Fiscal year")
    _, center, _ = st.columns([.7, 6, .7])
    center.plotly_chart(figure, width="stretch")

    growth_chart = px.bar(company, x="fiscal_year", y=company["revenue_growth"] * 100, color_discrete_sequence=["#087f5b"], text_auto=".1f")
    style_figure(growth_chart, title="Revenue growth · year over year", height=330)
    growth_chart.update_xaxes(dtick=1, title="Fiscal year")
    growth_chart.update_yaxes(title="Percent", ticksuffix="%")
    growth_chart.update_traces(texttemplate="%{y:.1f}%", textposition="outside", cliponaxis=False)
    _, center, _ = st.columns([1, 5.5, 1])
    center.plotly_chart(growth_chart, width="stretch")

    margin_data = company.melt(id_vars=["fiscal_year"], value_vars=["operating_margin", "net_margin", "fcf_margin", "capex_intensity"], var_name="metric", value_name="ratio")
    margin_data["Percent"] = margin_data["ratio"] * 100
    margin_figure = px.line(margin_data, x="fiscal_year", y="Percent", color="metric", markers=True, color_discrete_sequence=["#087f5b", "#173f32", "#76b89d", "#d97706"])
    style_figure(margin_figure, title="Margins and reinvestment intensity", height=370)
    margin_figure.update_xaxes(dtick=1, title="Fiscal year")
    margin_figure.update_yaxes(title="Percent", ticksuffix="%")
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

    with st.expander("Detailed financial data appendix"):
        st.dataframe(company, hide_index=True, width="stretch")

with cash_tab:
    st.subheader("Cash conversion, reinvestment and accounting quality")
    cash_data = company.melt(id_vars=["fiscal_year"], value_vars=["operating_cash_flow", "capex", "free_cash_flow"], var_name="metric", value_name="value")
    cash_data["USD billions"] = cash_data["value"] / 1e9
    cash_figure = px.bar(cash_data, x="fiscal_year", y="USD billions", color="metric", barmode="group", color_discrete_sequence=["#087f5b", "#d97706", "#76b89d"])
    style_figure(cash_figure, title="Cash generation versus investment", height=380)
    cash_figure.update_xaxes(dtick=1, title="Fiscal year")
    cash_figure.update_yaxes(title="USD billions")
    _, center, _ = st.columns([.7, 6, .7])
    center.plotly_chart(cash_figure, width="stretch")
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
        style_figure(waterfall, title="Reported-to-analytical cash-flow bridge", height=380)
        waterfall.update_layout(showlegend=False)
        waterfall.update_yaxes(title="USD billions")
        _, center, _ = st.columns([1.3, 5, 1.3])
        center.plotly_chart(waterfall, width="stretch")
        st.info("This adjustment is an analytical view, not a restatement. Confirm the lease note and keep definitions consistent across periods and peers.")
    else:
        st.info("No sourced normalization adjustment is preloaded. Any new adjustment requires source evidence.")

with peer_tab:
    st.subheader("Peer benchmarking and competitive position")
    st.caption("Quantitative comparisons use the latest available fiscal year and remain directional when business mix or fiscal calendars differ.")
    if len(peer_summary) > 1:
        compare = [name for name in ["revenue_growth", "operating_margin", "net_margin", "fcf_margin", "capex_intensity"] if name in peer_summary.columns]
        peer_chart = peer_summary.melt(id_vars=["ticker"], value_vars=compare, var_name="metric", value_name="ratio")
        peer_chart["Percent"] = peer_chart["ratio"] * 100
        peer_figure = px.bar(peer_chart, x="metric", y="Percent", color="ticker", barmode="group", color_discrete_sequence=["#087f5b", "#76b89d"])
        style_figure(peer_figure, title="Latest reported operating comparison", height=390)
        peer_figure.update_yaxes(title="Percent", ticksuffix="%")
        peer_figure.update_xaxes(title="")
        _, center, _ = st.columns([.7, 6, .7])
        center.plotly_chart(peer_figure, width="stretch")
    competitive = competitive_frame(profile)
    radar = go.Figure()
    dimensions = list(profile["competitive_dimensions"])
    for company_name, group in competitive.groupby("company", sort=False):
        values = group.set_index("dimension").reindex(dimensions)["score"].tolist()
        radar.add_trace(go.Scatterpolar(r=values + values[:1], theta=dimensions + dimensions[:1], fill="toself" if company_name in {summary["company"].split()[0], ticker, "Microsoft", "Oracle"} else None, name=company_name, opacity=.78))
    radar.update_layout(polar={"radialaxis":{"visible":True,"range":[0,5],"tickfont":{"color":"#3d5148"}},"angularaxis":{"tickfont":{"color":"#263d33"}},"bgcolor":"white"})
    style_figure(radar, title="Competitive rubric · analyst judgment, 1–5", height=470)
    _, center, _ = st.columns([.9, 5.8, .9])
    center.plotly_chart(radar, width="stretch")
    st.caption("The competitive rubric is an explicit analytical judgment, not a reported fact. It is designed to make assumptions visible and revisable.")

assumptions: dict[str, object] = {}
with scenario_tab:
    st.subheader("Operating scenarios and valuation sensitivity")
    st.caption("Scenario outputs are transparent assumptions - not market data, a target price or a recommendation.")
    scenario_plot = scenario_frame.melt(id_vars=["case"], value_vars=["revenue", "operating_income"], var_name="metric", value_name="value")
    scenario_plot["USD billions"] = scenario_plot["value"] / 1e9
    scenario_figure = px.bar(scenario_plot, x="case", y="USD billions", color="metric", barmode="group", color_discrete_sequence=["#087f5b", "#76b89d"], text_auto=".1f")
    style_figure(scenario_figure, title=f"Illustrative {int(scenario_frame.iloc[0]['years'])}-year operating outcomes", height=370)
    scenario_figure.update_xaxes(title="Scenario")
    scenario_figure.update_yaxes(title="USD billions")
    _, center, _ = st.columns([.8, 5.8, .8])
    center.plotly_chart(scenario_figure, width="stretch")
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
        style_figure(heat_figure, title="IRR sensitivity · user assumptions", height=380)
        _, center, _ = st.columns([1.4, 4.5, 1.4])
        center.plotly_chart(heat_figure, width="stretch")
    else:
        st.error("No positive base metric is available for the scenario model.")

with risk_tab:
    st.subheader("Catalysts, risks and monitoring agenda")
    st.markdown("<div class='section-deck'>The useful output is not a static conclusion. It is a falsifiable monitoring system: defined upside events, downside events and the indicators that reveal which path is developing.</div>", unsafe_allow_html=True)
    left, right = st.columns(2)
    left.markdown("### Potential catalysts")
    right.markdown("### Downside risks")
    for index in range(max(len(profile["catalysts"]), len(profile["risks"]))):
        if index < len(profile["catalysts"]):
            left.markdown(f"<div class='compact-card'><strong>CATALYST {index + 1:02d}</strong><p>{profile['catalysts'][index]}</p></div>", unsafe_allow_html=True)
        if index < len(profile["risks"]):
            right.markdown(f"<div class='compact-card'><strong>RISK {index + 1:02d}</strong><p>{profile['risks'][index]}</p></div>", unsafe_allow_html=True)
    st.markdown("### Monitoring dashboard")
    columns = st.columns(len(profile["monitoring_signals"]))
    for column, (label, signal) in zip(columns, profile["monitoring_signals"]):
        column.markdown(f"<div class='compact-card'><strong>{label.upper()}</strong><p>{signal}</p></div>", unsafe_allow_html=True)
    st.markdown("### Priority diligence")
    for item in profile["diligence_questions"]:
        st.write(f"- {item}")

with evidence_tab:
    audit = build_research_audit(scope, assumptions=assumptions)
    queue = review_queue(scope)
    st.subheader("Evidence coverage")
    coverage = pd.DataFrame({"Measure":["Core facts","Source metadata","Fact provenance"], "Percent":[100*(audit["metrics"]["core_fact_completeness"]["ratio"] or 0),100*(audit["metrics"]["source_filing_metadata_coverage"]["ratio"] or 0),100*(audit["metrics"]["fact_provenance_coverage"]["ratio"] or 0)]})
    coverage_figure = px.bar(coverage, x="Percent", y="Measure", orientation="h", color_discrete_sequence=["#087f5b"], text_auto=".0f")
    style_figure(coverage_figure, title="Evidence coverage", height=300)
    coverage_figure.update_xaxes(ticksuffix="%", range=[0,100], title="Percent")
    coverage_figure.update_yaxes(title="")
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
