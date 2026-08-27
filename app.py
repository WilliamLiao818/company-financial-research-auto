from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from company_profiles import accounting_quality_signals, fcf_bridge, profile_for
from fmp_connector import FmpConnectionError, FmpInputError, load_financial_statements
from input_pipeline import online_company_facts, parse_identifiers
from pdf_export import build_company_pdf
from research import (
    VALUATION_METRICS,
    financial_health_prompts,
    latest_company_summary,
    latest_peer_comparison,
    load_financials,
    quality_flags,
    scenario_sensitivity,
    valuation_scenario,
)
from research_catalog import (
    CIKS,
    COMPANY_NAMES,
    market_share_snapshot,
    sec_filings_url,
    target_price_snapshot,
)
from sec_connector import SecConfigurationError, SecConnectionError, SecInputError


SHOWCASES = COMPANY_NAMES
PEER_MAP = {
    "MSFT": ["ORCL", "GOOG"],
    "ORCL": ["MSFT", "GOOG"],
    "GOOG": ["MSFT", "ORCL"],
    "AVGO": ["NVDA"],
    "NVDA": ["AVGO"],
    "SNDK": [],
}
METRIC_LABELS = {
    "revenue": "Revenue",
    "operating_income": "Operating Income",
    "net_income": "Net Income",
    "operating_cash_flow": "Operating Cash Flow",
    "capex": "Capital Expenditure",
    "free_cash_flow": "Free Cash Flow",
    "gross_margin": "Gross Margin",
    "operating_margin": "Operating Margin",
    "net_margin": "Net Margin",
    "fcf_margin": "FCF Margin",
    "capex_intensity": "Capex Intensity",
    "revenue_growth": "Revenue Growth",
}


st.set_page_config(page_title="The Company · Version 2.0", page_icon="C", layout="wide", initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
    :root { --green:#087f5b; --deep:#0b2a20; --ink:#17372c; --muted:#52685e; --soft:#edf7f2; --line:#d4e2db; --amber:#d97706; }
    .stApp { background:#fbfdfc; color:var(--deep); }
    .block-container { max-width:1160px; padding-top:1.6rem; padding-bottom:4rem; }
    [data-testid="stHeader"] { background:rgba(251,253,252,.93); backdrop-filter:blur(18px); }
    [data-testid="stAppViewContainer"] p,
    [data-testid="stAppViewContainer"] label,
    [data-testid="stAppViewContainer"] li,
    [data-testid="stAppViewContainer"] span { color:var(--deep); }
    [data-testid="stCaptionContainer"] p { color:var(--muted)!important; font-size:.9rem!important; }
    h1 { font-family:Georgia,serif!important; font-weight:400!important; letter-spacing:-.045em!important; font-size:clamp(2.7rem,6vw,4.8rem)!important; line-height:1!important; }
    h2 { font-size:1.9rem!important; margin-top:1.6rem!important; letter-spacing:-.035em!important; }
    h3 { letter-spacing:-.025em!important; }
    div[data-testid="stMetric"] { padding:18px; background:white; border:1px solid var(--line); border-radius:16px; box-shadow:0 8px 24px rgba(11,42,32,.04); animation:rise .55s cubic-bezier(.22,1,.36,1) both; }
    div[data-testid="stMetricLabel"] p { color:var(--muted)!important; font-size:.86rem!important; }
    div[data-testid="stMetricValue"] { color:var(--green); font-size:1.72rem; }
    .stButton>button,.stDownloadButton>button,.stLinkButton>a { min-height:46px; border:0!important; border-radius:12px!important; color:white!important; background:var(--green)!important; font-weight:700!important; transition:.2s ease; }
    .stButton>button:hover,.stDownloadButton>button:hover,.stLinkButton>a:hover { background:#065f46!important; transform:translateY(-1px); }
    .stButton>button p,.stDownloadButton>button p,.stLinkButton>a p { color:white!important; }
    div[data-baseweb="tab-list"] { gap:2px; border-bottom:1px solid var(--line); overflow-x:auto; }
    button[data-baseweb="tab"] { padding:12px 13px; color:#40584d!important; white-space:nowrap; }
    button[data-baseweb="tab"] p { color:inherit!important; font-weight:700!important; }
    button[data-baseweb="tab"][aria-selected="true"] { color:var(--green)!important; }
    .hero-note { padding:18px 20px; border-left:3px solid var(--green); background:var(--soft); border-radius:0 14px 14px 0; color:var(--ink); font-size:15px; line-height:1.65; }
    .company-card,.story-card,.signal-card,.compact-card,.provider-card { height:100%; padding:21px; border:1px solid var(--line); border-radius:18px; background:white; box-shadow:0 10px 32px rgba(11,42,32,.035); }
    .company-card strong,.story-card strong,.signal-card strong,.compact-card strong,.provider-card strong { display:block; margin-bottom:9px; color:var(--green); font-size:12px; letter-spacing:.09em; }
    .company-card p,.story-card p,.signal-card p,.compact-card p,.provider-card p { margin:0; color:var(--muted)!important; font-size:14.5px; line-height:1.6; }
    .company-card { min-height:152px; }
    .story-card { min-height:175px; }
    .signal-card { min-height:205px; }
    .compact-card { min-height:126px; }
    .provider-card { min-height:145px; }
    .section-deck { max-width:790px; color:var(--muted); font-size:15px; line-height:1.7; margin-bottom:1rem; }
    .research-strip { padding:16px 19px; border:1px solid var(--line); border-radius:14px; background:white; color:var(--deep); font-size:14px; line-height:1.7; }
    .research-strip b { color:var(--green); }
    .source-note { padding:12px 15px; background:#f5f9f7; border-radius:12px; color:var(--muted); font-size:13px; line-height:1.6; }
    @keyframes rise { from { transform:translateY(10px); opacity:0; } to { transform:none; opacity:1; } }
    @keyframes barGrow { from { transform:scaleY(.02); opacity:.25; } to { transform:scaleY(1); opacity:1; } }
    @keyframes lineDraw { to { stroke-dashoffset:0; } }
    .js-plotly-plot .barlayer path { transform-box:fill-box; transform-origin:center bottom; animation:barGrow .8s cubic-bezier(.22,1,.36,1) both; }
    .js-plotly-plot .scatterlayer path.js-line { stroke-dasharray:1500; stroke-dashoffset:1500; animation:lineDraw 1.05s ease-out forwards; }
    @media (prefers-reduced-motion:reduce) { * { animation-duration:.01ms!important; transition-duration:.01ms!important; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def percent(value: object) -> str:
    return "—" if value is None or pd.isna(value) else f"{float(value):.1%}"


def usd_billions(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    amount = float(value) / 1e9
    return f"-${abs(amount):,.1f}B" if amount < 0 else f"${amount:,.1f}B"


def safe_name(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum() or character in "-_")


def humanize(name: object) -> str:
    raw = str(name)
    return METRIC_LABELS.get(raw, raw.replace("_", " ").title())


def style_figure(figure: go.Figure, *, title: str | None = None, height: int = 360, legend: str = "h") -> go.Figure:
    figure.update_layout(
        title={"text": title, "font": {"size": 20, "color": "#0b2a20"}, "x": .02} if title else None,
        height=height,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font={"family": "Arial, sans-serif", "size": 14, "color": "#27453a"},
        legend={"title": {"text": ""}, "orientation": legend, "yanchor": "bottom", "y": 1.02, "x": .02, "font": {"size": 13}},
        hoverlabel={"bgcolor": "#0b2a20", "font": {"color": "white", "size": 13}},
        margin={"l": 64, "r": 34, "t": 78 if title else 44, "b": 58},
        transition={"duration": 600, "easing": "cubic-in-out"},
    )
    figure.update_xaxes(showline=True, linecolor="#c6d7ce", gridcolor="#edf3f0", tickfont={"color": "#40584d", "size": 13}, title_font={"color": "#27453a", "size": 14}, zerolinecolor="#c6d7ce")
    figure.update_yaxes(showline=False, gridcolor="#e5eee9", tickfont={"color": "#40584d", "size": 13}, title_font={"color": "#27453a", "size": 14}, zerolinecolor="#c6d7ce")
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


def resolve_showcase(query: str) -> str | None:
    cleaned = query.strip().lower()
    if not cleaned:
        return None
    for ticker, name in SHOWCASES.items():
        if cleaned == ticker.lower() or cleaned in name.lower():
            return ticker
    return None


def open_company(ticker: str, data: pd.DataFrame | None = None) -> None:
    st.session_state["selected_ticker"] = ticker
    st.session_state["active_report"] = True
    if data is not None:
        st.session_state["custom_data"] = data
    st.query_params["ticker"] = ticker
    st.rerun()


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


def render_custom_loader(query: str) -> None:
    st.markdown("### Analyze another U.S.-listed company")
    st.markdown(
        "<div class='source-note'><b>Why a key?</b> SEC filings are public, but reliable company-name search and normalized statements at scale require a data provider. Your key is used only for this browser session and is never saved in the repository.</div>",
        unsafe_allow_html=True,
    )
    source = st.radio("Data path", ["Provider API · full statement history", "SEC Company Facts · core facts"], horizontal=True)
    if source.startswith("Provider"):
        api_key = st.text_input("Financial Modeling Prep API key", type="password", help="Create a key at financialmodelingprep.com. The system sends it directly to that provider for this request.")
        if st.button("Generate company view", type="primary", width="stretch"):
            try:
                with st.spinner("Loading annual statements…"):
                    frame = load_financial_statements(query, api_key, years=5)
                open_company(str(frame.iloc[-1]["ticker"]), frame)
            except (FmpInputError, FmpConnectionError, ValueError) as error:
                st.error(str(error))
    else:
        st.caption("Enter a ticker or CIK. This path does not require a commercial token; coverage follows standardized SEC XBRL tags and may omit company-specific metrics.")
        if st.button("Load SEC facts", type="primary", width="stretch"):
            try:
                with st.spinner("Loading SEC Company Facts…"):
                    frame = online_company_facts(parse_identifiers(query), years=5)
                open_company(str(frame.iloc[-1]["ticker"]), frame)
            except (SecInputError, SecConfigurationError, SecConnectionError, ValueError) as error:
                st.error(str(error))
    with st.expander("Three-step setup guide"):
        st.markdown("1. Create a Financial Modeling Prep account and copy your API key.\n\n2. Paste the key above and enter a U.S. ticker or company name.\n\n3. Generate the view. The key stays in session memory and is not written to GitHub or included in downloads.")
        links = st.columns(2)
        links[0].link_button("Provider API documentation", "https://site.financialmodelingprep.com/developer/docs", width="stretch")
        links[1].link_button("SEC Company Search", "https://www.sec.gov/edgar/search/", width="stretch")


def render_landing(prebuilt: pd.DataFrame) -> None:
    st.caption("THE COMPANY / FUNDAMENTALS, ACCOUNTING QUALITY & 12-MONTH VIEW · VERSION 2.0")
    st.title("Start with a company.")
    st.markdown("<div class='hero-note'>Search a ticker or company name. The six prebuilt U.S. public-company packs work immediately; any other U.S.-listed company can be loaded with a user-supplied provider key or through core SEC facts.</div>", unsafe_allow_html=True)
    query = st.text_input("Search ticker or company", placeholder="Try MSFT, Oracle, NVIDIA…", help="Currently supports U.S.-listed public companies.")
    if st.button("Open company", type="primary", width="stretch"):
        ticker = resolve_showcase(query)
        if ticker:
            open_company(ticker)
        elif query.strip():
            st.session_state["custom_query"] = query.strip()
        else:
            st.warning("Enter a ticker or company name.")
    st.caption("Currently supports U.S.-listed public companies. Prebuilt packs require no key.")
    custom_query = st.session_state.get("custom_query")
    if custom_query:
        render_custom_loader(str(custom_query))

    st.subheader("Prebuilt research packs")
    tickers = list(SHOWCASES)
    for start in range(0, len(tickers), 3):
        columns = st.columns(3)
        for column, ticker in zip(columns, tickers[start:start + 3]):
            summary = latest_company_summary(prebuilt, ticker)
            with column:
                st.markdown(f"<div class='company-card'><strong>{ticker} · PUBLIC FILINGS</strong><h3>{SHOWCASES[ticker]}</h3><p>FY{summary['fiscal_year']} · Revenue {usd_billions(summary['revenue'])}<br/>Operating margin {percent(summary['operating_margin'])}</p></div>", unsafe_allow_html=True)
                actions = st.columns(2)
                if actions[0].button("Open", key=f"open-{ticker}", width="stretch"):
                    open_company(ticker)
                actions[1].download_button("PDF", base_pdf(prebuilt, ticker), f"{ticker.lower()}-company-report.pdf", "application/pdf", key=f"pdf-{ticker}", width="stretch")


prebuilt = load_financials()
query_ticker = str(st.query_params.get("ticker", "")).upper()
if "active_report" not in st.session_state:
    st.session_state["active_report"] = query_ticker in SHOWCASES
if query_ticker in SHOWCASES:
    st.session_state["selected_ticker"] = query_ticker

if not st.session_state["active_report"]:
    render_landing(prebuilt)
    st.stop()

custom_data = st.session_state.get("custom_data")
ticker_hint = str(st.session_state.get("selected_ticker", "MSFT"))
if isinstance(custom_data, pd.DataFrame) and ticker_hint in set(custom_data["ticker"]):
    scope = custom_data.copy()
    selector_options = [ticker_hint, *SHOWCASES]
else:
    scope = prebuilt.copy()
    selector_options = list(SHOWCASES)

navigation = st.columns([1.15, 4.1, 1.4])
if navigation[0].button("← Company search", width="stretch"):
    st.session_state["active_report"] = False
    st.session_state.pop("custom_query", None)
    st.query_params.clear()
    st.rerun()
selected = navigation[1].selectbox("Company", selector_options, index=selector_options.index(ticker_hint) if ticker_hint in selector_options else 0, format_func=lambda item: f"{item} · {SHOWCASES.get(item, item)}")
if selected != ticker_hint:
    if selected in SHOWCASES:
        st.session_state.pop("custom_data", None)
    open_company(selected)
navigation[2].caption("U.S.-listed companies")

ticker = selected
if ticker in SHOWCASES and ticker not in set(scope["ticker"]):
    scope = prebuilt.copy()
company = scope.loc[scope["ticker"] == ticker].sort_values("fiscal_year")
summary = latest_company_summary(scope, ticker)
profile = profile_for(ticker)
signals = accounting_quality_signals(scope, ticker)
bridge = fcf_bridge(scope, ticker)
peer_summary = latest_peer_comparison(prebuilt if ticker in SHOWCASES else scope)
scenario_frame = operating_scenarios(company, profile)
pdf_bytes = build_company_pdf(company, summary, profile, signals, bridge, ticker=ticker, peers=peer_summary, scenarios=scenario_frame)

headline, download = st.columns([4.5, 1.5])
with headline:
    st.title(summary["company"])
    st.markdown(f"<div class='hero-note'><strong>{ticker}</strong> · FY{summary['fiscal_year']} · Public-source research architecture. Reported facts, deterministic calculations and analytical judgments remain visibly separate.</div>", unsafe_allow_html=True)
with download:
    st.write("")
    st.download_button("Download full PDF", pdf_bytes, f"{safe_name(ticker)}-company-report.pdf", "application/pdf", type="primary", width="stretch")
    st.caption("12-page detailed report")

filing_links = st.columns([1, 1, 4])
if ticker in CIKS:
    filing_links[0].link_button("Recent 10-K filings", sec_filings_url(ticker, "10-K"), width="stretch")
    filing_links[1].link_button("Recent 10-Q filings", sec_filings_url(ticker, "10-Q"), width="stretch")
else:
    filing_links[0].link_button("SEC filing search", f"https://www.sec.gov/edgar/search/#/q={ticker}", width="stretch")

metrics = st.columns(6)
metrics[0].metric("Revenue", usd_billions(summary["revenue"]), percent(summary["revenue_growth"]))
metrics[1].metric("Gross Margin", percent(summary["gross_margin"]))
metrics[2].metric("Operating Margin", percent(summary["operating_margin"]))
metrics[3].metric("Free Cash Flow", usd_billions(summary["free_cash_flow"]))
metrics[4].metric("Capex / Revenue", percent(summary["capex_intensity"]))
metrics[5].metric("Cash Conversion", "—" if pd.isna(summary["cash_conversion"]) else f"{summary['cash_conversion']:.2f}x")
if ticker == "ORCL":
    st.markdown("<div class='source-note'><b>Oracle gross margin:</b> derived from reported revenue less cloud/software, hardware and services direct costs. Oracle does not publish the standard GrossProfit XBRL tag used by many issuers.</div>", unsafe_allow_html=True)

executive_tab, business_tab, earnings_tab, cash_tab, competition_tab, target_tab, scenario_tab, risk_tab = st.tabs([
    "Executive view", "Business & moat", "Earnings", "Cash & quality", "Competition", "12-month view", "Scenario lab", "Catalysts & risks",
])

with executive_tab:
    st.subheader("Answer first")
    st.markdown("<div class='section-deck'>The opening view states what must be true, what could invalidate it and which questions should drive the next update.</div>", unsafe_allow_html=True)
    columns = st.columns(2)
    columns[0].markdown(f"<div class='story-card'><strong>THESIS</strong><p>{profile['research_thesis']}</p></div>", unsafe_allow_html=True)
    columns[1].markdown(f"<div class='story-card'><strong>COUNTER-THESIS</strong><p>{profile['counter_thesis']}</p></div>", unsafe_allow_html=True)
    st.subheader("Pivotal questions")
    questions = st.columns(min(3, len(profile["key_questions"])))
    for index, (column, question) in enumerate(zip(questions, profile["key_questions"]), start=1):
        column.markdown(f"<div class='compact-card'><strong>QUESTION {index:02d}</strong><p>{question}</p></div>", unsafe_allow_html=True)
    st.subheader("Latest read-through")
    st.markdown(f"<div class='research-strip'><b>Growth:</b> revenue changed {percent(summary['revenue_growth'])}. <b>Profitability:</b> gross margin is {percent(summary['gross_margin'])} and operating margin is {percent(summary['operating_margin'])}. <b>Reinvestment:</b> capex is {percent(summary['capex_intensity'])} of revenue. <b>Cash:</b> free cash flow is {usd_billions(summary['free_cash_flow'])}.</div>", unsafe_allow_html=True)

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
    st.markdown("### Indicators to monitor")
    st.write(" · ".join(profile["key_kpis"]))

with earnings_tab:
    st.subheader("Earnings power and operating trajectory")
    st.markdown("<div class='section-deck'>Scale, growth, profitability and reinvestment are separated so different economic signals do not collapse into one crowded chart.</div>", unsafe_allow_html=True)
    trend = company.melt(id_vars=["fiscal_year"], value_vars=["revenue", "operating_income", "free_cash_flow"], var_name="metric", value_name="value")
    trend["Metric"] = trend["metric"].map(humanize)
    trend["USD billions"] = trend["value"] / 1e9
    figure = px.line(trend, x="fiscal_year", y="USD billions", color="Metric", markers=True, color_discrete_sequence=["#087f5b", "#35a77c", "#173f32"])
    style_figure(figure, title="Scale and cash generation · USD billions", height=390)
    figure.update_xaxes(dtick=1, title="Fiscal Year")
    st.plotly_chart(figure, width="stretch")

    growth = company.loc[company["revenue_growth"].notna()].copy()
    growth["Revenue Growth"] = growth["revenue_growth"] * 100
    growth_chart = px.bar(growth, x="fiscal_year", y="Revenue Growth", color_discrete_sequence=["#087f5b"], text_auto=".1f")
    style_figure(growth_chart, title="Revenue growth · year over year", height=330)
    growth_chart.update_xaxes(dtick=1, title="Fiscal Year")
    growth_chart.update_yaxes(title="Percent", ticksuffix="%")
    growth_chart.update_traces(texttemplate="%{y:.1f}%", textposition="outside", cliponaxis=False)
    _, center, _ = st.columns([.7, 5.8, .7])
    center.plotly_chart(growth_chart, width="stretch")
    if len(company):
        st.caption(f"FY{int(company.iloc[0]['fiscal_year'])} is the starting year; year-over-year growth begins with the next comparable period.")

    profit_metrics = [name for name in ["gross_margin", "operating_margin", "net_margin"] if company[name].notna().any()]
    cash_metrics = [name for name in ["fcf_margin", "capex_intensity"] if company[name].notna().any()]
    chart_columns = st.columns(2)
    for column, names, title, palette in [
        (chart_columns[0], profit_metrics, "Profitability", ["#76b89d", "#087f5b", "#173f32"]),
        (chart_columns[1], cash_metrics, "Cash and reinvestment", ["#35a77c", "#d97706"]),
    ]:
        melted = company.melt(id_vars=["fiscal_year"], value_vars=names, var_name="metric", value_name="ratio")
        melted["Metric"] = melted["metric"].map(humanize)
        melted["Percent"] = melted["ratio"] * 100
        margin_figure = px.line(melted, x="fiscal_year", y="Percent", color="Metric", markers=True, color_discrete_sequence=palette)
        style_figure(margin_figure, title=title, height=360)
        margin_figure.update_xaxes(dtick=1, title="Fiscal Year")
        margin_figure.update_yaxes(title="Percent", ticksuffix="%")
        column.plotly_chart(margin_figure, width="stretch")

    prompts, quality = st.columns(2)
    with prompts:
        st.subheader("Questions raised by the trend")
        for item in financial_health_prompts(scope, ticker):
            st.write(f"- {item}")
    with quality:
        st.subheader("Data notes")
        flags = quality_flags(scope, ticker)
        if flags:
            for item in flags:
                st.write(f"- {humanize(item) if '_' in item else item}")
        else:
            st.success("Core annual statement fields are populated for the latest period.")

with cash_tab:
    st.subheader("Cash conversion, reinvestment and accounting quality")
    cash_data = company.melt(id_vars=["fiscal_year"], value_vars=["operating_cash_flow", "capex", "free_cash_flow"], var_name="metric", value_name="value")
    cash_data["Metric"] = cash_data["metric"].map(humanize)
    cash_data["USD billions"] = cash_data["value"] / 1e9
    cash_figure = px.bar(cash_data, x="fiscal_year", y="USD billions", color="Metric", barmode="group", color_discrete_sequence=["#087f5b", "#d97706", "#76b89d"])
    style_figure(cash_figure, title="Cash generation versus investment", height=390)
    cash_figure.update_xaxes(dtick=1, title="Fiscal Year")
    cash_figure.update_yaxes(title="USD Billions")
    st.plotly_chart(cash_figure, width="stretch")
    st.subheader("Noise filter")
    st.caption("Classification, timing and evidence checks identify review work; they do not allege misconduct.")
    if signals.empty:
        st.success("No deterministic signal was triggered. This does not establish accounting quality.")
    else:
        for start in range(0, len(signals), 2):
            columns = st.columns(2)
            for column, row in zip(columns, signals.iloc[start:start + 2].itertuples(index=False)):
                column.markdown(f"<div class='signal-card'><strong>{row.category.upper()} · {row.confidence.upper()}</strong><h3>{row.signal}</h3><p>{row.observation}<br/><br/><b>Implication:</b> {row.analytical_implication}<br/><br/><b>Next check:</b> {row.required_review}</p></div>", unsafe_allow_html=True)
    if len(bridge) > 1:
        st.subheader("Reported-to-analytical cash-flow bridge")
        waterfall = go.Figure(go.Waterfall(x=bridge["step"], y=bridge["amount_usd_billions"], measure=bridge["kind"], connector={"line":{"color":"#9db8ac"}}, increasing={"marker":{"color":"#087f5b"}}, decreasing={"marker":{"color":"#d97706"}}, totals={"marker":{"color":"#173f32"}}, text=[f"${value:,.1f}B" for value in bridge["amount_usd_billions"]], textposition="outside"))
        style_figure(waterfall, title="Reported-to-analytical cash-flow bridge", height=380)
        waterfall.update_layout(showlegend=False)
        waterfall.update_yaxes(title="USD Billions")
        _, center, _ = st.columns([1, 5.5, 1])
        center.plotly_chart(waterfall, width="stretch")
        st.info("This adjustment is an analytical view, not a restatement. Definitions must remain consistent across periods and peers.")

with competition_tab:
    st.subheader("Competitive position")
    st.markdown("<div class='section-deck'>Reported peer metrics, market share and a scored competitive rubric answer different questions; each carries its own source and boundary.</div>", unsafe_allow_html=True)
    relevant = [ticker, *PEER_MAP.get(ticker, [])]
    peer_view = peer_summary.loc[peer_summary["ticker"].isin(relevant)]
    if len(peer_view) > 1:
        compare = [name for name in ["revenue_growth", "operating_margin", "net_margin", "fcf_margin", "capex_intensity"] if name in peer_view.columns]
        peer_chart = peer_view.melt(id_vars=["ticker"], value_vars=compare, var_name="metric", value_name="ratio")
        peer_chart["Metric"] = peer_chart["metric"].map(humanize)
        peer_chart["Percent"] = peer_chart["ratio"] * 100
        peer_figure = px.bar(peer_chart, x="Metric", y="Percent", color="ticker", barmode="group", color_discrete_sequence=["#087f5b", "#76b89d", "#173f32"])
        style_figure(peer_figure, title="Latest reported operating comparison", height=390)
        peer_figure.update_yaxes(title="Percent", ticksuffix="%")
        peer_figure.update_xaxes(title="")
        st.plotly_chart(peer_figure, width="stretch")

    market = market_share_snapshot(ticker)
    competition_columns = st.columns([1, 1.25])
    if market["values"]:
        labels = list(market["values"])
        values = list(market["values"].values())
        donut = go.Figure(go.Pie(labels=labels, values=values, hole=.58, sort=False, textinfo="label+percent", textposition="outside", marker={"colors":["#087f5b", "#35a77c", "#76b89d", "#b7d8c9", "#dcebe4", "#d97706", "#9aaea4"]}))
        style_figure(donut, title=f"{market['title']} · {market['period']}", height=440)
        donut.update_layout(showlegend=False, margin={"l":45,"r":45,"t":86,"b":35})
        competition_columns[0].plotly_chart(donut, width="stretch")
        competition_columns[0].caption(f"Source: {market['source']}. {market['note']}")
        competition_columns[0].link_button("Open market-share source", str(market["source_url"]), width="stretch")

    scores = pd.DataFrame(profile["competitive_scores"], index=profile["competitive_dimensions"]).T
    heatmap = go.Figure(go.Heatmap(z=scores.values, x=list(scores.columns), y=list(scores.index), zmin=1, zmax=5, colorscale=[[0,"#edf7f2"],[.5,"#76b89d"],[1,"#087f5b"]], text=scores.values, texttemplate="%{text}/5", hovertemplate="%{y}<br>%{x}: %{z}/5<extra></extra>", colorbar={"title":"Score","tickvals":[1,2,3,4,5]}))
    style_figure(heatmap, title="Competitive rubric · explicit analyst judgment", height=440)
    heatmap.update_xaxes(title="", tickangle=-18)
    heatmap.update_yaxes(title="", autorange="reversed")
    competition_columns[1].plotly_chart(heatmap, width="stretch")
    competition_columns[1].caption("Read across a row to compare one company across dimensions; read down a column to compare competitors on one dimension. Scores are revisable judgments, not reported facts.")

with target_tab:
    target = target_price_snapshot(ticker)
    st.subheader("12-month price framework")
    st.markdown("<div class='section-deck'>Recent institutional targets are dated source observations. The Company range is a separate Bear/Base/Bull scenario output with an explicit analytical basis.</div>", unsafe_allow_html=True)
    if target["street"]:
        street = pd.DataFrame(target["street"])
        street["Label"] = street["firm"] + " · " + street["date"]
        street_figure = px.bar(street.sort_values("target"), x="target", y="Label", orientation="h", color_discrete_sequence=["#76b89d"], text="target")
        style_figure(street_figure, title="Recent institutional targets · USD per share", height=max(310, 70 * len(street)))
        street_figure.update_xaxes(title="USD per Share")
        street_figure.update_yaxes(title="")
        street_figure.update_traces(texttemplate="$%{x:,.0f}", textposition="outside", cliponaxis=False)
        st.plotly_chart(street_figure, width="stretch")
        st.caption(f"Snapshot through {target['as_of']}. Dates are the latest updates shown by the cited aggregator; verify against each institution's original publication where accessible.")
        st.link_button("Open target-price source", str(target["source_url"]), width="stretch")
        house = target["house"]
        cards = st.columns(3)
        for card, case in zip(cards, ["Bear", "Base", "Bull"]):
            card.metric(f"The Company · {case}", f"${house[case]:,.0f}")
        st.markdown(f"<div class='source-note'><b>Range basis:</b> {target['basis']} Scenarios are not recommendations or probabilities.</div>", unsafe_allow_html=True)
    else:
        st.info("A dated target-price snapshot is not prebuilt for this company. Provider coverage is required before this section can be populated responsibly.")

with scenario_tab:
    st.subheader("Operating scenarios and valuation sensitivity")
    st.caption("Scenario outputs are transparent assumptions, not market data or recommendations.")
    scenario_plot = scenario_frame.melt(id_vars=["case"], value_vars=["revenue", "operating_income"], var_name="metric", value_name="value")
    scenario_plot["Metric"] = scenario_plot["metric"].map(humanize)
    scenario_plot["USD billions"] = scenario_plot["value"] / 1e9
    scenario_figure = px.bar(scenario_plot, x="case", y="USD billions", color="Metric", barmode="group", color_discrete_sequence=["#087f5b", "#76b89d"], text_auto=".1f")
    style_figure(scenario_figure, title=f"Illustrative {int(scenario_frame.iloc[0]['years'])}-year operating outcomes", height=370)
    scenario_figure.update_xaxes(title="Scenario")
    scenario_figure.update_yaxes(title="USD Billions")
    st.plotly_chart(scenario_figure, width="stretch")
    latest = company.iloc[-1]
    available_metrics = [name for name in VALUATION_METRICS if name in latest.index and pd.notna(latest[name]) and latest[name] > 0]
    if available_metrics:
        metric = st.selectbox("Base metric", available_metrics, format_func=lambda name: humanize(name))
        base_value = float(latest[metric] / 1e9)
        inputs = st.columns(4)
        years = int(inputs[0].number_input("Years", 1, 10, 5, 1))
        growth_rate = inputs[1].number_input("Annual growth · %", -50.0, 100.0, 10.0, 1.0) / 100
        entry_multiple = inputs[2].number_input("Entry multiple", min_value=.1, value=10.0, step=.5)
        exit_multiple = inputs[3].number_input("Exit multiple", min_value=.1, value=10.0, step=.5)
        scenario = valuation_scenario(base_metric_value=base_value, metric=metric, annual_growth_rate=growth_rate, holding_period_years=years, entry_multiple=entry_multiple, exit_multiple=exit_multiple, entry_net_debt=0, exit_net_debt=0)
        results = st.columns(4)
        results[0].metric("Entry equity value", f"${scenario['entry_equity_value']:,.1f}B")
        results[1].metric("Exit equity value", f"${scenario['exit_equity_value']:,.1f}B")
        results[2].metric("MOIC", f"{scenario['moic']:.2f}x")
        results[3].metric("IRR", f"{scenario['irr']:.1%}")
        sensitivity = scenario_sensitivity(base_metric_value=base_value, metric=metric, annual_growth_rates=[max(-.99,growth_rate-.05),growth_rate,growth_rate+.05], holding_period_years=years, entry_multiple=entry_multiple, exit_multiples=[max(.1,exit_multiple-2),exit_multiple,exit_multiple+2], entry_net_debt=0, exit_net_debt=0)
        heat = sensitivity.pivot(index="annual_growth_rate", columns="exit_multiple", values="irr") * 100
        x_labels = [f"{float(value):.1f}x" for value in heat.columns]
        y_labels = [f"{float(value):.0%}" for value in heat.index]
        heat_figure = go.Figure(go.Heatmap(z=heat.values, x=x_labels, y=y_labels, text=heat.values, texttemplate="%{text:.1f}%", colorscale=[[0,"#e8f5ef"],[1,"#087f5b"]], colorbar={"title":"IRR"}, hovertemplate="Growth %{y}<br>Exit %{x}<br>IRR %{z:.1f}%<extra></extra>"))
        style_figure(heat_figure, title="IRR sensitivity · user assumptions", height=360)
        heat_figure.update_xaxes(title="Exit Multiple", type="category")
        heat_figure.update_yaxes(title="Annual Growth", type="category")
        _, center, _ = st.columns([1.1, 5, 1.1])
        center.plotly_chart(heat_figure, width="stretch")

with risk_tab:
    st.subheader("Catalysts, risks and monitoring agenda")
    st.markdown("<div class='section-deck'>A useful view is falsifiable and updateable: defined upside events, downside events and the indicators that reveal which path is developing.</div>", unsafe_allow_html=True)
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

st.caption("Public-source research support. Missing values remain missing. Scenarios and target-price ranges are analytical outputs, not recommendations or transaction instructions.")
