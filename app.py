from __future__ import annotations

import importlib
from functools import partial
from html import escape

import market_data as market_data_module
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from company_profiles import accounting_quality_signals, fcf_bridge, profile_for
from news_connector import load_company_news_snapshot
from stress_model import Assumptions, FORMULA, PRESETS, case_record, preset_cases, scenario_note
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
    COMPANY_ROLES,
    COMPANY_SECTORS,
    EXPANDED_PEERS,
    FOREIGN_PRIVATE_ISSUERS,
    latest_results_snapshot,
    market_share_snapshot,
    sec_filings_url,
    target_price_snapshot,
)
from data_health import latest_filing


# Streamlit Cloud can retain imported helpers during a hot deployment. Reloading
# this small module keeps the benchmark schema synchronized with the CSV snapshot.
market_data_module = importlib.reload(market_data_module)
load_market_performance = market_data_module.load_market_performance
performance_summary = market_data_module.performance_summary
performance_context_note = market_data_module.performance_context_note


SHOWCASES = COMPANY_NAMES
COMPANY_TICKERS_AZ = tuple(
    sorted(SHOWCASES, key=lambda ticker: (SHOWCASES[ticker].casefold(), ticker))
)
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


st.set_page_config(page_title="Company research · Research Desk", page_icon="R", layout="wide", initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
    :root { color-scheme:light only; }
    :root { --green:#087f5b; --deep:#0b2a20; --ink:#17372c; --muted:#52685e; --soft:#edf7f2; --line:#d4e2db; --amber:#d97706; }
    .stApp { background:#fbfdfc; color:var(--deep); }
    .block-container { max-width:1160px; padding-top:1.6rem; padding-bottom:4rem; }
    header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stAppDeployButton"], footer, #MainMenu { display:none!important; visibility:hidden!important; height:0!important; }
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
    .selection-pill { display:inline-flex; align-items:center; gap:8px; margin:.25rem 0 .75rem; padding:8px 12px; border-radius:999px; background:var(--soft); color:var(--green); font-weight:700; font-size:13px; }
    .news-card { height:100%; overflow:hidden; border:1px solid var(--line); border-radius:18px; background:white; box-shadow:0 10px 32px rgba(11,42,32,.035); }
    .news-card img { width:100%; height:132px; object-fit:cover; display:block; }
    .news-card .news-copy { padding:16px 17px 18px; }
    .news-card .news-meta { color:var(--green)!important; font-weight:700; font-size:11px; letter-spacing:.04em; }
    .news-card h4 { margin:8px 0 0; color:var(--deep); font-size:16px; line-height:1.35; }
    .news-card a { text-decoration:none; }
    [data-testid="stAppViewContainer"], [data-testid="stMain"], .stApp { background:#fbfdfc!important; }
    .st-key-pro_masthead {
        --deep:#f2f7ef; --muted:#c1d5ca;
        padding:clamp(1.3rem,4vw,3.2rem); border-radius:18px;
        background:linear-gradient(115deg,#0a2720,#164337); border:1px solid #214b3f;
    }
    .st-key-pro_masthead h1 { color:var(--deep); margin:0; }
    .st-key-lite_masthead [data-testid="stCaptionContainer"] a { color:var(--green); }
    .st-key-pro_masthead [data-testid="stCaptionContainer"] a,
    .st-key-pro_masthead [data-testid="stMarkdownContainer"] a { color:#d4eddb; }
    .st-key-pro_masthead [data-testid="stDownloadButton"] button {
        background:#e4f1e8!important; color:#10382b!important;
    }
    .st-key-pro_masthead [data-testid="stDownloadButton"] button:hover { background:#fff!important; }
    .st-key-pro_masthead [data-testid="stDownloadButton"] button p { color:#10382b!important; }
    .st-key-pro_results div[data-testid="stMetric"] {
        --muted:#c1d5ca; --green:#f0f8ef;
        border-color:#284c40; background:#12392e; box-shadow:none;
    }
    .st-key-pro_results [data-testid="stMetricValue"] * { color:var(--green); }
    @keyframes rise { from { transform:translateY(10px); opacity:0; } to { transform:none; opacity:1; } }
    @keyframes barGrow { from { transform:scaleY(.02); opacity:.25; } to { transform:scaleY(1); opacity:1; } }
    @keyframes lineDraw {
        0% { stroke-dasharray:3000; stroke-dashoffset:3000; }
        99% { stroke-dasharray:3000; stroke-dashoffset:0; }
        100% { stroke-dasharray:none; stroke-dashoffset:0; }
    }
    .js-plotly-plot .barlayer path { transform-box:fill-box; transform-origin:center bottom; animation:barGrow .8s cubic-bezier(.22,1,.36,1) both; }
    .js-plotly-plot .scatterlayer path.js-line { animation:lineDraw 1.05s ease-out forwards; }
    @media (prefers-reduced-motion:reduce) { * { animation-duration:.01ms!important; transition-duration:.01ms!important; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def percent(value: object) -> str:
    return "—" if value is None or pd.isna(value) else f"{float(value):.1%}"


def money_billions(value: object, currency: str = "USD") -> str:
    if value is None or pd.isna(value):
        return "—"
    symbol = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "TWD": "NT$"}.get(str(currency), f"{currency} ")
    amount = float(value) / 1e9
    return f"-{symbol}{abs(amount):,.1f}B" if amount < 0 else f"{symbol}{amount:,.1f}B"


def safe_name(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum() or character in "-_")


def humanize(name: object) -> str:
    raw = str(name)
    return METRIC_LABELS.get(raw, raw.replace("_", " ").title())


def style_figure(figure: go.Figure, *, title: str | None = None, height: int = 360, legend: str = "h") -> go.Figure:
    figure.update_layout(template=None)
    figure.update_layout(
        title={"text": title, "font": {"size": 20, "color": "#0b2a20"}, "x": .02, "y": .98, "yanchor": "top"} if title else None,
        height=height,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font={"family": "Arial, sans-serif", "size": 14, "color": "#27453a"},
        legend={"title": {"text": ""}, "orientation": legend, "yanchor": "bottom", "y": 1.025, "x": .02, "font": {"size": 12, "color": "#27453a"}, "bgcolor": "rgba(255,255,255,.92)"},
        hoverlabel={"bgcolor": "white", "bordercolor": "#76b89d", "font": {"color": "#0b2a20", "size": 13, "family": "Arial, sans-serif"}, "align": "left"},
        hovermode="closest",
        margin={"l": 68, "r": 46, "t": 126 if title else 58, "b": 66},
        uniformtext={"minsize": 11, "mode": "hide"},
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


def signed_money(value: float, currency: str) -> str:
    return f"{'+' if value > 0 else ''}{money_billions(value, currency)}"


def reset_case(case_key: str) -> None:
    for key in list(st.session_state):
        if key == case_key or key.startswith(f"{case_key}:"):
            del st.session_state[key]


def render_stress_test(summary: dict, profile: dict, pro: bool) -> None:
    st.subheader("Valuation stress test")
    revenue = summary["revenue"]
    if pd.isna(revenue) or revenue <= 0:
        st.info("This test needs a positive reported annual revenue figure.")
        return
    ticker, currency = summary["ticker"], str(summary["currency"])
    st.caption("See how a change in demand, profitability or valuation affects the business at the end of the same period.")
    linked_preset = st.query_params.get("preset")
    initial_index = PRESETS.index(linked_preset) if linked_preset in PRESETS else 0
    preset = st.selectbox("Stress to apply", PRESETS, index=initial_index, key=f"preset:{ticker}")
    if preset != (linked_preset or PRESETS[0]):
        st.query_params["preset"] = preset
    defaults = profile["scenario_defaults"]
    base, stress = preset_cases(defaults, preset)
    years = int(defaults["years"])
    if pro:
        # Keep the last edit locally in this Streamlit session when a widget is hidden.
        case_key = f"case:{ticker}:{summary['fiscal_year_end']}:{preset}"
        saved = st.session_state.get(case_key, {})
        years = int(st.number_input("Years from the reported fiscal year", 1, 10, saved.get("years", years), key=f"{case_key}:years"))
        cases = []
        for column, label, default in zip(st.columns(2), ("Base", "Stress"), (base, stress)):
            column.markdown(f"**{label} assumptions**")
            inputs = saved.get(label, default)
            growth = column.number_input(f"{label} annual growth (%)", -95., 200., round(inputs.growth * 100, 4), step=.5, key=f"{case_key}:{label}:growth")
            margin = column.number_input(f"{label} terminal margin (%)", -100., 100., round(inputs.margin * 100, 4), step=.5, key=f"{case_key}:{label}:margin")
            multiple = column.number_input(f"{label} exit multiple (×)", .1, 200., float(inputs.multiple), step=.5, key=f"{case_key}:{label}:multiple")
            cases.append(Assumptions(growth / 100, margin / 100, multiple))
        base, stress = cases
        st.session_state[case_key] = {"years": years, "Base": base, "Stress": stress}
        st.button("Reset this preset", on_click=reset_case, args=(case_key,), key=f"reset:{case_key}")
    else:
        st.markdown(
            f"**{years}-year assumptions**  ·  Annual growth {base.growth:.1%} → {stress.growth:.1%}  ·  "
            f"Operating margin {base.margin:.1%} → {stress.margin:.1%}  ·  Exit multiple {base.multiple:g}× → {stress.multiple:g}×"
        )
    record = case_record(summary, years, base, stress, preset)
    outputs = record["outputs"]
    cards = st.container(key="pro_results" if pro else "lite_results").columns(3)
    for card, label in zip(cards[:2], ("Base", "Stress")):
        value = outputs[label.lower()]["enterprise_value"]
        card.metric(f"{label} terminal EV", money_billions(value, currency) if value is not None else "N/M")
    diff = outputs["difference"]
    cards[2].metric("Change from base", signed_money(diff, currency) if diff is not None else "N/M",
                    None if diff is None else f"{outputs['relative_difference']:+.1%}")
    if diff is None:
        st.info("A positive operating-profit multiple needs positive terminal operating profit. "
                f"The projected profits are {money_billions(outputs['base']['operating_profit'], currency)} (base) "
                f"and {money_billions(outputs['stress']['operating_profit'], currency)} (stress).")
    elif pro:
        lines = [f"**{label}** {signed_money(value, currency)}" for label, value in outputs["contributions"].items()]
        st.markdown(" · ".join(lines))
        st.caption("Each step replaces one base assumption in the order shown. The three changes add to the total before rounding.")
    if pro:
        st.table(pd.DataFrame([
            {"Projection": label, "Base": money_billions(outputs["base"][key], currency),
             "Stress": money_billions(outputs["stress"][key], currency)}
            for key, label in (("revenue", "Terminal revenue"), ("operating_profit", "Terminal operating profit"))
        ]).set_index("Projection"))
    st.caption(f"Reported starting revenue {money_billions(revenue, currency)} · FY ended {summary['fiscal_year_end']} · {currency}.")
    with st.expander("Trace the calculation"):
        st.write(FORMULA)
        st.write(f"The company profile supplies illustrative base and bear growth and margin assumptions. "
                 f"The starting EV/operating profit multiple is an illustrative 15×, reduced to 12× for a multiple shock. "
                 f"Both outcomes are terminal enterprise values in {currency}, before discounting or net debt.")
        st.write(record["currency_basis"])
        filed = record["reported_facts"]["filed"]
        filing_label = f"Filed {filed}" if filed else "Filing date unavailable"
        st.markdown(f"{filing_label}. [Open the public financial record]({summary['source_url']})")
    st.download_button("Save this scenario", scenario_note(record),
                       file_name=f"{ticker.lower()}-fy{summary['fiscal_year']}-stress.md", mime="text/markdown",
                       key=f"download-stress:{ticker}", on_click="ignore",
                       help="Keep the reported input, source, assumptions, formula and results together.")


def render_peers(ticker: str, mode: str) -> None:
    peers = EXPANDED_PEERS.get(ticker, ())
    if peers:
        links = [f"[{peer} · {SHOWCASES[peer]}](?ticker={peer}&mode={mode.lower()})" for peer in peers]
        st.markdown("**Compare with**  " + "  ·  ".join(links))


def render_news(ticker: str) -> None:
    stories = load_company_news_snapshot(ticker, limit=4)
    if stories:
        for start in range(0, len(stories), 2):
            columns = st.columns(2)
            for column, story in zip(columns, stories[start:start + 2]):
                image = f"<img class='article-image' src='{escape(story['image'], quote=True)}' alt='{escape(story['title'], quote=True)}'/>" if story.get("image") else ""
                card = (
                    f"<div class='news-card'>{image}<div class='news-copy'>"
                    f"<div class='news-meta'>{escape(story['publisher'])} · {escape(story['date'])}</div>"
                    f"<a href='{escape(story['url'], quote=True)}' target='_blank' rel='noopener'><h4>{escape(story['title'])}</h4></a>"
                    "</div></div>"
                )
                column.markdown(card, unsafe_allow_html=True)
    else:
        st.info("No qualifying article was available from the monitored publications during the latest 90 days.")


def open_company(ticker: str) -> None:
    st.query_params["ticker"] = ticker
    st.rerun()


def company_report_data(frame: pd.DataFrame, ticker: str) -> bytes:
    company = frame.loc[frame["ticker"] == ticker].sort_values("fiscal_year")
    profile = profile_for(ticker)
    return build_company_pdf(
        company, latest_company_summary(frame, ticker), profile, accounting_quality_signals(frame, ticker),
        fcf_bridge(frame, ticker), ticker=ticker, peers=latest_peer_comparison(frame),
        scenarios=operating_scenarios(company, profile),
    )


def render_landing(prebuilt: pd.DataFrame, pro: bool) -> None:
    with st.container(key="pro_masthead" if pro else "lite_masthead"):
        st.markdown("[Research Desk](https://liaoresearch.com/)")
        st.title("Start with a company.")
    query = st.selectbox(
        "Search ticker or company",
        options=list(COMPANY_TICKERS_AZ),
        index=None,
        placeholder="Type a ticker or company name, then select a match",
        format_func=lambda item: f"{item} · {SHOWCASES[item]}",
    )
    if st.button("Open company", type="primary", width="stretch", disabled=query is None):
        open_company(query)

    st.subheader(f"{len(SHOWCASES)} prebuilt research packs")
    sector_options = ["All sectors", *sorted(set(COMPANY_SECTORS.values()), key=str.casefold)]
    selected_sector = st.selectbox("Sector", sector_options)
    tickers = [
        ticker
        for ticker in COMPANY_TICKERS_AZ
        if selected_sector == "All sectors" or COMPANY_SECTORS[ticker] == selected_sector
    ]
    st.caption(
        f"{len(tickers)} companies · Sorted A–Z by company name · "
        "PDFs are available after opening a company."
    )
    for start in range(0, len(tickers), 3):
        columns = st.columns(3)
        for column, ticker in zip(columns, tickers[start:start + 3]):
            summary = latest_company_summary(prebuilt, ticker)
            latest_result = latest_results_snapshot(ticker)
            latest_line = (
                f"<br/>Quarter on file {latest_result['label']}"
                if latest_result["label"] else ""
            )
            with column:
                st.markdown(
                    f"<div class='company-card'><strong>{ticker}</strong><h3>{SHOWCASES[ticker]}</h3>"
                    f"<p>Latest annual FY{summary['fiscal_year']} · Revenue {money_billions(summary['revenue'], summary.get('currency', 'USD'))}"
                    f"<br/>Operating margin {percent(summary['operating_margin'])}"
                    f"{latest_line}</p></div>",
                    unsafe_allow_html=True,
                )
                if st.button("Open", key=f"open-{ticker}", width="stretch"):
                    open_company(ticker)


prebuilt = load_financials()
ticker = str(st.query_params.get("ticker", "")).strip().upper()
if ticker not in SHOWCASES:
    if ticker:
        st.info("This company is outside current coverage. Choose a covered company below.")
    render_landing(prebuilt, str(st.query_params.get("mode", "")).lower() == "pro")
    st.stop()

navigation = st.columns([1.2, 3.7, 1.6])
if navigation[0].button("Company search", width="stretch"):
    st.query_params.from_dict({"mode": "pro"} if st.query_params.get("mode") == "pro" else {})
    st.rerun()
selected = navigation[1].selectbox("Company", COMPANY_TICKERS_AZ, index=COMPANY_TICKERS_AZ.index(ticker),
                                   format_func=lambda item: f"{item} · {SHOWCASES[item]}")
if selected != ticker:
    open_company(selected)
navigation[2].link_button("Research Desk home", "https://liaoresearch.com/", width="stretch")
mode = st.radio("Research mode", ("Lite", "Pro"), horizontal=True,
                           index=int(str(st.query_params.get("mode", "")).lower() == "pro"),
                           key=f"mode:{ticker}")
if mode.lower() != str(st.query_params.get("mode", "lite")).lower():
    st.query_params["mode"] = mode.lower()

scope = prebuilt
company = scope.loc[scope["ticker"] == ticker].sort_values("fiscal_year")
summary = latest_company_summary(scope, ticker)
profile = profile_for(ticker)
currency = str(summary["currency"])

header = st.container(key="pro_masthead" if mode == "Pro" else "lite_masthead")
headline, download = header.columns([4.5, 1.5], vertical_alignment="center")
with headline:
    st.title(summary["company"])
    quote_url = f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}"
    st.caption(
        f"{ticker} · [View share price on Nasdaq]({quote_url}) · {COMPANY_ROLES[ticker]} · "
        f"FY{summary['fiscal_year']} ended {summary['fiscal_year_end']}"
    )
    filing = latest_filing(ticker)
    if filing:
        st.markdown(f"[Latest filing on file · {filing['form']} · {filing['filed']}]({filing['url']})")

with download:
    st.download_button("Download full PDF", partial(company_report_data, scope, ticker),
                       f"{safe_name(ticker)}-company-report.pdf", "application/pdf",
                       type="primary", width="stretch", on_click="ignore")

if mode == "Lite":
    top = st.columns(3)
    top[0].metric("Annual revenue", money_billions(summary["revenue"], currency), percent(summary["revenue_growth"]))
    top[1].metric("Operating margin", percent(summary["operating_margin"]))
    top[2].metric("Free cash flow", money_billions(summary["free_cash_flow"], currency))
    st.subheader("The research question")
    st.write(profile["key_questions"][0])
    st.markdown(f"**Thesis**  {profile['research_thesis']}")
    st.markdown(f"**What could change it**  {profile['counter_thesis']}")
    render_stress_test(summary, profile, pro=False)
    render_peers(ticker, mode)
    with st.expander("News from the past 90 days"):
        render_news(ticker)
    st.stop()

signals = accounting_quality_signals(scope, ticker)
bridge = fcf_bridge(scope, ticker)
peer_summary = latest_peer_comparison(prebuilt)
scenario_frame = operating_scenarios(company, profile)
render_stress_test(summary, profile, pro=True)

filing_links = st.columns([1, 1, 1.25, 2.75])
latest_result = latest_results_snapshot(ticker)
provider_quarter = latest_result.get("source_kind") == "provider"
if ticker in CIKS:
    annual_form, interim_form = (("20-F", "6-K") if ticker in FOREIGN_PRIVATE_ISSUERS else ("10-K", "10-Q"))
    filing_links[0].link_button(f"Recent {annual_form} filings", sec_filings_url(ticker, annual_form), width="stretch")
    filing_links[1].link_button(f"Recent {interim_form} filings", sec_filings_url(ticker, interim_form), width="stretch")
    if latest_result["url"]:
        filing_links[2].link_button(f"{'Provider results' if provider_quarter else 'Filed results'} · {latest_result['label']}", latest_result["url"], width="stretch")
else:
    filing_links[0].link_button("SEC filing search", f"https://www.sec.gov/edgar/search/#/q={ticker}", width="stretch")
if latest_result["url"]:
    if provider_quarter:
        st.caption(f"Yahoo Finance quarterly statement · reporting month {latest_result['period_end'][:7]}.")
    else:
        st.caption(f"Quarter on file · {latest_result['label']} ({latest_result['form']}) · "
                   f"period ended {latest_result['period_end']} · filed {latest_result['filed']}.")
if latest_result.get("revenue") is not None:
    st.markdown(f"### Quarter on file · {latest_result['label']}")
    latest_currency = str(latest_result["currency"])
    latest_metrics = st.columns(3)
    for column, key in zip(latest_metrics, ("revenue", "operating_income", "net_income")):
        value = latest_result.get(key)
        column.metric(f"Reported {humanize(key)}", money_billions(float(value) * 1e6 if value is not None else None, latest_currency))
    if not provider_quarter:
        st.caption(
            f"Reported currency ({latest_currency}) · three-month period {latest_result['period_start']} to "
            f"{latest_result['period_end']}."
        )
    if latest_result.get("note"):
        st.markdown(f"<div class='source-note'>{latest_result['note']}</div>", unsafe_allow_html=True)

st.markdown("### Latest annual fundamentals")
metrics = st.columns(6)
currency = str(summary.get("currency", "USD"))
currency_label = {"USD": "USD", "EUR": "EUR", "GBP": "GBP", "JPY": "JPY", "TWD": "TWD"}.get(currency, currency)
currency_symbol = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "TWD": "NT$"}.get(currency, f"{currency} ")
metrics[0].metric("Revenue", money_billions(summary["revenue"], currency), percent(summary["revenue_growth"]))
metrics[1].metric("Gross Margin", percent(summary["gross_margin"]))
metrics[2].metric("Operating Margin", percent(summary["operating_margin"]))
metrics[3].metric("Free Cash Flow", money_billions(summary["free_cash_flow"], currency))
metrics[4].metric("Capex / Revenue", percent(summary["capex_intensity"]))
metrics[5].metric("Cash Conversion", "—" if pd.isna(summary["cash_conversion"]) else f"{summary['cash_conversion']:.2f}x")
if ticker == "ORCL":
    st.markdown("<div class='source-note'><b>Oracle gross margin:</b> derived from reported revenue less cloud/software, hardware and services direct costs. Oracle does not publish the standard GrossProfit XBRL tag used by many issuers.</div>", unsafe_allow_html=True)

overview_tab, business_tab, financials_tab, competition_tab, performance_tab, valuation_tab, risk_tab = st.tabs([
    "Overview", "Business & moat", "Financials & quality", "Competition", "Market performance", "Valuation & scenarios", "Catalysts & risks",
])
executive_tab = overview_tab
earnings_tab = financials_tab
cash_tab = financials_tab
target_tab = valuation_tab
scenario_tab = valuation_tab

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
    st.subheader("Latest annual read-through")
    st.markdown(f"<div class='research-strip'><b>Growth:</b> revenue changed {percent(summary['revenue_growth'])}. <b>Profitability:</b> gross margin is {percent(summary['gross_margin'])} and operating margin is {percent(summary['operating_margin'])}. <b>Reinvestment:</b> capex is {percent(summary['capex_intensity'])} of revenue. <b>Cash:</b> free cash flow is {money_billions(summary['free_cash_flow'], currency)}.</div>", unsafe_allow_html=True)
    st.subheader("Three-month news monitor")
    render_news(ticker)

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
    trend[f"{currency_label} billions"] = trend["value"] / 1e9
    figure = px.line(trend, x="fiscal_year", y=f"{currency_label} billions", color="Metric", markers=True, color_discrete_sequence=["#087f5b", "#35a77c", "#173f32"])
    style_figure(figure, title=f"Scale and cash generation · {currency_label} billions", height=390)
    figure.update_xaxes(dtick=1, title="Fiscal Year")
    figure.update_traces(hovertemplate=f"<b>%{{fullData.name}}</b><br>Fiscal Year %{{x}}<br>%{{y:,.1f}} {currency_label}B<extra></extra>")
    st.plotly_chart(figure, width="stretch", theme=None)

    growth = company.loc[company["revenue_growth"].notna()].copy()
    growth["Revenue Growth"] = growth["revenue_growth"] * 100
    growth_chart = px.bar(growth, x="fiscal_year", y="Revenue Growth", color_discrete_sequence=["#087f5b"], text_auto=".1f")
    style_figure(growth_chart, title="Revenue growth · year over year", height=330)
    growth_chart.update_xaxes(dtick=1, title="Fiscal Year")
    growth_chart.update_yaxes(title="Percent", ticksuffix="%")
    growth_minimum = min(0.0, float(growth["Revenue Growth"].min()))
    growth_maximum = max(0.0, float(growth["Revenue Growth"].max()))
    growth_padding = max(1.0, (growth_maximum - growth_minimum) * 0.18)
    growth_chart.update_yaxes(range=[growth_minimum - growth_padding, growth_maximum + growth_padding])
    growth_chart.update_traces(texttemplate="%{y:.1f}%", textposition="outside", cliponaxis=False, hovertemplate="<b>Revenue Growth</b><br>Fiscal Year %{x}<br>%{y:.1f}%<extra></extra>")
    _, center, _ = st.columns([.7, 5.8, .7])
    center.plotly_chart(growth_chart, width="stretch", theme=None)
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
        margin_figure.update_xaxes(dtick=1, title="Fiscal Year", range=[float(company["fiscal_year"].min()) - .25, float(company["fiscal_year"].max()) + .25], automargin=True)
        margin_figure.update_yaxes(title="Percent", ticksuffix="%")
        margin_figure.update_traces(hovertemplate="<b>%{fullData.name}</b><br>Fiscal Year %{x}<br>%{y:.1f}%<extra></extra>")
        column.plotly_chart(margin_figure, width="stretch", theme=None)

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
    cash_data[f"{currency_label} billions"] = cash_data["value"] / 1e9
    cash_figure = px.bar(cash_data, x="fiscal_year", y=f"{currency_label} billions", color="Metric", barmode="group", color_discrete_sequence=["#087f5b", "#d97706", "#76b89d"])
    style_figure(cash_figure, title="Cash generation versus investment", height=390)
    cash_figure.update_xaxes(dtick=1, title="Fiscal Year")
    cash_figure.update_yaxes(title=f"{currency_label} Billions")
    cash_figure.update_traces(hovertemplate=f"<b>%{{fullData.name}}</b><br>Fiscal Year %{{x}}<br>%{{y:,.1f}} {currency_label}B<extra></extra>")
    st.plotly_chart(cash_figure, width="stretch", theme=None)
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
        waterfall.update_traces(hovertemplate="<b>%{x}</b><br>%{y:,.1f} USD B<extra></extra>")
        _, center, _ = st.columns([1, 5.5, 1])
        center.plotly_chart(waterfall, width="stretch", theme=None)
        st.info("This adjustment is an analytical view, not a restatement. Definitions must remain consistent across periods and peers.")

with competition_tab:
    st.subheader("Competitive position")
    render_peers(ticker, mode)
    st.markdown("<div class='section-deck'>Peer metrics, market share and a scored competitive rubric answer different questions and should be read separately.</div>", unsafe_allow_html=True)
    relevant = [ticker, *EXPANDED_PEERS.get(ticker, [])]
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
        peer_figure.update_traces(hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>%{y:.1f}%<extra></extra>")
        st.plotly_chart(peer_figure, width="stretch", theme=None)

    market = market_share_snapshot(ticker)
    competition_columns = st.columns([1, 1.25])
    if market["values"]:
        labels = list(market["values"])
        values = list(market["values"].values())
        legend_labels = [f"{label} · {value:.0f}%" for label, value in zip(labels, values)]
        donut = go.Figure(go.Pie(labels=legend_labels, customdata=labels, values=values, hole=.62, sort=False, textinfo="none", hovertemplate="<b>%{customdata}</b><br>%{value:.1f}%<extra></extra>", marker={"colors":["#087f5b", "#35a77c", "#76b89d", "#b7d8c9", "#dcebe4", "#d97706", "#9aaea4"]}))
        style_figure(donut, title=f"{market['title']} · {market['period']}", height=440)
        donut.update_layout(showlegend=True, legend={"orientation":"h", "yanchor":"top", "y":-.04, "x":0, "font":{"size":11,"color":"#27453a"}, "bgcolor":"rgba(255,255,255,.94)"}, margin={"l":35,"r":35,"t":115,"b":112})
        competition_columns[0].plotly_chart(donut, width="stretch", theme=None)
        reference_label = "Historical reference — not a current market-share estimate. " if market.get("historical") else ""
        competition_columns[0].caption(f"{reference_label}Data through {market['period']}. {market.get('note', '')}")

    if profile["competitive_scores"] and profile["competitive_dimensions"]:
        scores = pd.DataFrame(profile["competitive_scores"], index=profile["competitive_dimensions"]).T
        heatmap = go.Figure(go.Heatmap(z=scores.values, x=list(scores.columns), y=list(scores.index), zmin=1, zmax=5, colorscale=[[0,"#edf7f2"],[.5,"#76b89d"],[1,"#087f5b"]], text=scores.values, texttemplate="%{text}/5", hovertemplate="%{y}<br>%{x}: %{z}/5<extra></extra>", colorbar={"title":"Score","tickvals":[1,2,3,4,5]}))
        style_figure(heatmap, title="Competitive rubric · explicit analyst judgment", height=440)
        heatmap.update_xaxes(title="", tickangle=-18)
        heatmap.update_yaxes(title="", autorange="reversed")
        competition_columns[1].plotly_chart(heatmap, width="stretch", theme=None)
        competition_columns[1].caption("Read across a row to compare one company across dimensions. Application Reach measures the breadth of first-party business applications and installed workflows available to distribute adjacent cloud, data and AI services. All 1–5 scores are revisable analyst judgments, not market-share data.")

with performance_tab:
    st.subheader("Long-term market performance")
    history = load_market_performance(ticker)
    if history.empty:
        st.info("A comparable market-history window is not available for this company.")
    else:
        history_figure = px.line(history, x="date", y="growth_of_100", color="series", custom_data=["adjusted_close"], color_discrete_map={ticker:"#087f5b", "SPY":"#173f32", "QQQ":"#76b89d"})
        style_figure(history_figure, title="Growth of 100 · adjusted monthly performance", height=430)
        history_figure.update_xaxes(title="")
        history_figure.update_yaxes(title="Growth of 100")
        history_figure.update_traces(hovertemplate="<b>%{fullData.name}</b><br>%{x|%b %Y}<br>Adjusted price %{customdata[0]:,.2f}<extra></extra>")
        history_figure.update_layout(hovermode="closest", hoverdistance=24)
        st.plotly_chart(history_figure, width="stretch", theme=None)
        performance_rows = performance_summary(history)
        cards = st.columns(len(performance_rows))
        for card, row in zip(cards, performance_rows):
            card.metric(str(row["series"]), f"{float(row['total_return']):+.1%}", f"{float(row['annualized_return']):.1%} annualized")
        first_date = pd.Timestamp(history["date"].min()).date().isoformat()
        last_date = pd.Timestamp(history["date"].max()).date().isoformat()
        st.caption(f"Common comparison window: {first_date} to {last_date}. The window shortens automatically when a company has less than ten years of trading history.")
        if note := performance_context_note(ticker):
            st.caption(note)

with target_tab:
    target = target_price_snapshot(ticker)
    st.subheader("12-month price framework")
    st.markdown("<div class='section-deck'>Recent institutional targets are dated market observations. The Company range is a separate Bear/Base/Bull scenario output with an explicit analytical basis.</div>", unsafe_allow_html=True)
    if target["street"] and not target.get("stale"):
        street = pd.DataFrame(target["street"])
        street["Label"] = street["firm"] + " · " + street["date"]
        street_figure = px.bar(street.sort_values("target"), x="target", y="Label", orientation="h", color_discrete_sequence=["#76b89d"], text="target")
        style_figure(street_figure, title="Recent institutional targets · USD per share", height=max(310, 70 * len(street)))
        street_figure.update_xaxes(title="USD per Share")
        street_figure.update_yaxes(title="")
        street_figure.update_traces(texttemplate="$%{x:,.0f}", textposition="outside", cliponaxis=False)
        street_figure.update_traces(hovertemplate="<b>%{y}</b><br>$%{x:,.0f} per share<extra></extra>")
        street_figure.update_yaxes(automargin=True)
        street_figure.update_xaxes(range=[0, float(street["target"].max()) * 1.18])
        st.plotly_chart(street_figure, width="stretch", theme=None)
        st.caption(f"Target observations updated through {target['as_of']}.")
        house = target["house"]
        cards = st.columns(3)
        for card, case in zip(cards, ["Bear", "Base", "Bull"]):
            card.metric(f"The Company · {case}", f"${house[case]:,.0f}")
        st.markdown(f"<div class='source-note'><b>Range basis:</b> {target['basis']} Scenarios are not recommendations or probabilities.</div>", unsafe_allow_html=True)
    elif target.get("stale"):
        st.info(f"The prior target-price observations expired after 45 days (last updated {target['as_of']}) and are hidden until a newly dated, verifiable set is available.")
    else:
        st.info("A dated target-price snapshot is not prebuilt for this company. Provider coverage is required before this section can be populated responsibly.")

with scenario_tab:
    st.subheader("Operating scenarios and valuation sensitivity")
    st.caption("Scenario outputs are transparent assumptions, not market data or recommendations.")
    scenario_plot = scenario_frame.melt(id_vars=["case"], value_vars=["revenue", "operating_income"], var_name="metric", value_name="value")
    scenario_plot["Metric"] = scenario_plot["metric"].map(humanize)
    scenario_plot[f"{currency_label} billions"] = scenario_plot["value"] / 1e9
    scenario_figure = px.bar(scenario_plot, x="case", y=f"{currency_label} billions", color="Metric", barmode="group", color_discrete_sequence=["#087f5b", "#76b89d"], text_auto=".1f")
    style_figure(scenario_figure, title=f"Illustrative {int(scenario_frame.iloc[0]['years'])}-year operating outcomes", height=370)
    scenario_figure.update_xaxes(title="Scenario")
    scenario_figure.update_yaxes(title=f"{currency_label} Billions")
    scenario_maximum = float((scenario_plot[f"{currency_label} billions"]).max())
    scenario_minimum = min(0.0, float(scenario_plot[f"{currency_label} billions"].min()))
    scenario_figure.update_yaxes(range=[scenario_minimum * 1.24, scenario_maximum * 1.24])
    scenario_figure.update_traces(texttemplate="%{y:.1f}", textposition="outside", cliponaxis=False, hovertemplate=f"<b>%{{fullData.name}}</b><br>%{{x}}<br>%{{y:,.1f}} {currency_label}B<extra></extra>")
    st.plotly_chart(scenario_figure, width="stretch", theme=None)
    latest = company.iloc[-1]
    available_metrics = [name for name in VALUATION_METRICS if name in latest.index and pd.notna(latest[name]) and latest[name] > 0]
    if available_metrics:
        st.markdown("<div class='source-note'><b>How to use:</b> choose the operating metric, holding period, growth rate and entry/exit multiples. The cards show the resulting return; the matrix shows how IRR changes across growth and exit-multiple assumptions.</div>", unsafe_allow_html=True)
        metric = st.selectbox("Base metric", available_metrics, format_func=lambda name: humanize(name))
        base_value = float(latest[metric] / 1e9)
        inputs = st.columns(4)
        years = int(inputs[0].number_input("Years", 1, 10, 5, 1))
        growth_rate = inputs[1].number_input("Annual growth · %", -50.0, 100.0, 10.0, 1.0) / 100
        entry_multiple = inputs[2].number_input("Entry multiple", min_value=.1, value=10.0, step=.5)
        exit_multiple = inputs[3].number_input("Exit multiple", min_value=.1, value=10.0, step=.5)
        scenario = valuation_scenario(base_metric_value=base_value, metric=metric, annual_growth_rate=growth_rate, holding_period_years=years, entry_multiple=entry_multiple, exit_multiple=exit_multiple, entry_net_debt=0, exit_net_debt=0)
        results = st.columns(4)
        results[0].metric("Entry equity value", f"{currency_symbol}{scenario['entry_equity_value']:,.1f}B")
        results[1].metric("Exit equity value", f"{currency_symbol}{scenario['exit_equity_value']:,.1f}B")
        results[2].metric("MOIC", f"{scenario['moic']:.2f}x")
        results[3].metric("IRR", f"{scenario['irr']:.1%}")
        sensitivity = scenario_sensitivity(base_metric_value=base_value, metric=metric, annual_growth_rates=sorted({max(-.99,growth_rate-.05),growth_rate,growth_rate+.05}), holding_period_years=years, entry_multiple=entry_multiple, exit_multiples=sorted({max(.1,exit_multiple-2),exit_multiple,exit_multiple+2}), entry_net_debt=0, exit_net_debt=0)
        heat = sensitivity.pivot(index="annual_growth_rate", columns="exit_multiple", values="irr") * 100
        x_labels = [f"{float(value):.1f}x" for value in heat.columns]
        y_labels = [f"{float(value):.0%}" for value in heat.index]
        heat_figure = go.Figure(go.Heatmap(z=heat.values, x=x_labels, y=y_labels, text=heat.values, texttemplate="%{text:.1f}%", colorscale=[[0,"#e8f5ef"],[1,"#087f5b"]], colorbar={"title":"IRR"}, hovertemplate="Growth %{y}<br>Exit %{x}<br>IRR %{z:.1f}%<extra></extra>"))
        style_figure(heat_figure, title="IRR sensitivity · user assumptions", height=360)
        heat_figure.update_xaxes(title="Exit Multiple", type="category")
        heat_figure.update_yaxes(title="Annual Growth", type="category")
        _, center, _ = st.columns([1.1, 5, 1.1])
        center.plotly_chart(heat_figure, width="stretch", theme=None)

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
