from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from input_pipeline import (
    company_facts_json_from_bytes,
    financial_csv_from_bytes,
    online_company_facts,
    parse_identifiers,
)
from research import (
    DATA_PATH,
    VALUATION_METRICS,
    assumption_ledger,
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
    scenario_sensitivity,
    source_ledger,
    valuation_scenario,
)
from sec_connector import SecConfigurationError, SecConnectionError, SecInputError


st.set_page_config(page_title="Company Financial Research Auto", page_icon="📊", layout="wide")
st.title("Company Financial Research Auto")
st.caption(
    "美国SEC公开年度财务研究：用户输入 → 申报事实 → 透明公式 → 用户选择的比较与情景 → 可下载报告。"
)
st.warning("不支持全球任意公司；缺失或不兼容的XBRL事实保持缺失，系统不会猜数，也不提供投资建议。")


def percent(value) -> str:
    return "—" if value is None or pd.isna(value) else f"{value:.1%}"


def usd_billions(value) -> str:
    return "—" if value is None or pd.isna(value) else f"${value / 1e9:,.1f}B"


MODE_BY_LABEL = {
    "冻结Demo（离线）": "frozen_demo",
    "在线SEC：Ticker/CIK": "online_sec",
    "上传SEC Company Facts JSON": "uploaded_sec_json",
    "上传同结构财务CSV": "uploaded_csv",
}

st.sidebar.header("输入")
mode_label = st.sidebar.radio("数据模式", list(MODE_BY_LABEL), index=0)
input_mode = MODE_BY_LABEL[mode_label]
current_year = date.today().year
year_columns = st.sidebar.columns(2)
start_year = int(
    year_columns[0].number_input("起始财年", min_value=2000, max_value=current_year + 1, value=current_year - 4)
)
end_year = int(
    year_columns[1].number_input("结束财年", min_value=2000, max_value=current_year + 1, value=current_year)
)
if start_year > end_year:
    st.error("起始财年不能晚于结束财年。")
    st.stop()

data: pd.DataFrame | None = None
try:
    if input_mode == "frozen_demo":
        data = load_financials()
        st.sidebar.caption("内置Microsoft、Oracle、NVIDIA冻结样例；无需联网或密钥。")

    elif input_mode == "online_sec":
        raw_identifiers = st.sidebar.text_area(
            "Ticker/CIK（逗号或换行分隔，最多5个）",
            value="MSFT, ORCL, NVDA",
            help="Ticker需要在线读取SEC ticker映射；纯数字或CIK前缀会直接按CIK读取。",
        )
        request_key = (raw_identifiers, start_year, end_year)
        if st.sidebar.button("从SEC加载", type="primary"):
            identifiers = parse_identifiers(raw_identifiers)
            with st.spinner("正在读取SEC Company Facts…"):
                loaded = online_company_facts(identifiers, years=20)
            st.session_state["online_sec_request"] = request_key
            st.session_state["online_sec_data"] = loaded
        if st.session_state.get("online_sec_request") == request_key:
            data = st.session_state.get("online_sec_data")
        if data is None:
            st.info(
                "在线模式需要先点击“从SEC加载”。若环境未配置SEC_USER_AGENT或无法联网，"
                "请使用冻结Demo或上传已保存的SEC JSON/财务CSV。"
            )
            st.stop()

    elif input_mode == "uploaded_sec_json":
        uploaded_json = st.sidebar.file_uploader("SEC Company Facts JSON", type=["json"])
        ticker_override = st.sidebar.text_input(
            "可选Ticker标签",
            help="只改变页面显示标签，不改变JSON内CIK、公司名或财务事实。",
        )
        st.sidebar.caption("文件仅在当前Streamlit会话内解析，不写入仓库或磁盘。")
        if uploaded_json is None:
            st.info("请选择一份从SEC Company Facts保存的JSON文件。")
            st.stop()
        data = company_facts_json_from_bytes(
            uploaded_json.getvalue(), ticker=ticker_override.strip() or None, years=20
        )

    else:
        uploaded_csv = st.sidebar.file_uploader("财务CSV", type=["csv"])
        st.sidebar.download_button(
            "下载CSV结构示例",
            DATA_PATH.read_bytes(),
            file_name="financials-template.csv",
            mime="text/csv",
        )
        st.sidebar.caption("文件仅在当前Streamlit会话内解析，不写入仓库或磁盘。")
        if uploaded_csv is None:
            st.info("请上传与示例字段一致的财务CSV；来源URL和日期字段为必填。")
            st.stop()
        data = financial_csv_from_bytes(uploaded_csv.getvalue())

    data = filter_year_range(data, start_year, end_year)
except (ValueError, SecInputError, SecConfigurationError, SecConnectionError) as error:
    st.error(str(error))
    st.caption("没有生成替代数字。请检查输入、年份、网络或SEC_USER_AGENT后重试。")
    st.stop()

available_tickers = sorted(data["ticker"].unique())
st.sidebar.header("研究范围")
ticker = st.sidebar.selectbox("主要公司", available_tickers)
peer_options = [item for item in available_tickers if item != ticker]
peer_tickers = st.sidebar.multiselect("比较公司（由用户选择）", peer_options, default=peer_options)
scope_tickers = [ticker, *peer_tickers]
scope_data = data.loc[data["ticker"].isin(scope_tickers)].copy()
company = scope_data.loc[scope_data["ticker"] == ticker].sort_values("fiscal_year")
latest = company.iloc[-1]
summary = latest_company_summary(scope_data, ticker)

scenario = None
assumptions: dict[str, object] = {}

overview_tab, peers_tab, scenario_tab, sources_tab = st.tabs(
    [
        "1. 财务趋势与提示",
        "2. 用户选择的年度比较",
        "3. 估值与回报情景",
        "4. 证据、公式与报告",
    ]
)

with overview_tab:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("最新年度营收", usd_billions(summary["revenue"]), percent(summary["revenue_growth"]))
    col2.metric("营业利润率", percent(summary["operating_margin"]))
    col3.metric("简化自由现金流", usd_billions(summary["free_cash_flow"]))
    col4.metric("资本开支/营收", percent(summary["capex_intensity"]))

    trend = company.melt(
        id_vars=["fiscal_year"],
        value_vars=["revenue", "operating_income", "net_income", "free_cash_flow"],
        var_name="metric",
        value_name="value",
    )
    trend["value_usd_billions"] = trend["value"] / 1e9
    chart = px.line(
        trend,
        x="fiscal_year",
        y="value_usd_billions",
        color="metric",
        markers=True,
        labels={"fiscal_year": "Fiscal year", "value_usd_billions": "USD billions"},
    )
    st.plotly_chart(chart, width="stretch")

    display_columns = [
        "fiscal_year",
        "fiscal_year_end",
        "revenue_growth",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "fcf_margin",
        "capex_intensity",
        "cash_conversion",
        "debt_to_assets_proxy",
    ]
    st.dataframe(
        company[display_columns].style.format(
            {
                "revenue_growth": "{:.1%}",
                "gross_margin": "{:.1%}",
                "operating_margin": "{:.1%}",
                "net_margin": "{:.1%}",
                "fcf_margin": "{:.1%}",
                "capex_intensity": "{:.1%}",
                "cash_conversion": "{:.2f}x",
                "debt_to_assets_proxy": "{:.1%}",
            },
            na_rep="—",
        ),
        width="stretch",
    )
    left, right = st.columns(2)
    with left:
        st.subheader("规则化财务观察点")
        st.caption("规则只提出核查问题，不构成公司评级。")
        for item in financial_health_prompts(scope_data, ticker):
            st.write(f"- {item}")
    with right:
        st.subheader("数据质量检查")
        for item in quality_flags(scope_data, ticker):
            st.write(f"- {item}")

with peers_tab:
    st.info(
        "比较集合完全由用户选择。财年截止日和业务结构可能不同，本表不是自动识别的严格可比公司组。"
    )
    peers = latest_peer_comparison(scope_data)
    peer_columns = [
        "ticker",
        "company",
        "fiscal_year_end",
        "revenue_growth",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "fcf_margin",
        "capex_intensity",
        "cash_conversion",
        "debt_to_assets_proxy",
    ]
    st.dataframe(
        peers[peer_columns].style.format(
            {
                "revenue_growth": "{:.1%}",
                "gross_margin": "{:.1%}",
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

with scenario_tab:
    st.warning(
        "公开申报事实只提供基期指标；增长率、进出场倍数、持有期和净债务均为用户假设。"
        "情景不是实时市场估值、DCF、目标价或投资建议。"
    )
    available_metrics = [
        name
        for name in VALUATION_METRICS
        if name in latest.index and pd.notna(latest[name]) and latest[name] > 0
    ]
    if not available_metrics:
        st.error("当前公司没有可用于正值倍数情景的基期指标。")
    else:
        metric = st.selectbox(
            "估值基准指标",
            available_metrics,
            format_func=lambda name: VALUATION_METRICS[name]["label"],
        )
        base_value = float(latest[metric] / 1e9)
        st.metric("公开事实：基期指标", f"${base_value:,.1f}B")
        col1, col2, col3 = st.columns(3)
        years = int(col1.number_input("持有期（年）", 1, 10, 5, 1))
        growth_pct = col2.number_input("指标年增长假设（%）", -50.0, 100.0, 10.0, 1.0)
        entry_multiple = col3.number_input("进场倍数", min_value=0.1, value=10.0, step=0.5)
        col4, col5, col6 = st.columns(3)
        exit_multiple = col4.number_input("退出倍数", min_value=0.1, value=10.0, step=0.5)
        entry_net_debt = col5.number_input("进场净债务（USD B）", value=0.0, step=1.0)
        exit_net_debt = col6.number_input("退出净债务（USD B）", value=0.0, step=1.0)
        growth_rate = growth_pct / 100
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
            st.error(f"当前用户假设无法计算：{error}")

        st.subheader("用户假设账本")
        st.dataframe(assumption_ledger(assumptions), hide_index=True, width="stretch")
        if scenario:
            result1, result2, result3, result4 = st.columns(4)
            result1.metric("进场股权价值", f"${scenario['entry_equity_value']:,.1f}B")
            result2.metric("退出股权价值", f"${scenario['exit_equity_value']:,.1f}B")
            result3.metric("MOIC", f"{scenario['moic']:.2f}x")
            result4.metric("IRR", f"{scenario['irr']:.1%}")
            growth_points = sorted({max(-0.99, growth_rate - 0.05), growth_rate, growth_rate + 0.05})
            multiple_points = sorted({max(0.1, exit_multiple - 2), exit_multiple, exit_multiple + 2})
            sensitivity = scenario_sensitivity(
                base_metric_value=base_value,
                metric=metric,
                annual_growth_rates=growth_points,
                holding_period_years=years,
                entry_multiple=entry_multiple,
                exit_multiples=multiple_points,
                entry_net_debt=entry_net_debt,
                exit_net_debt=exit_net_debt,
            )
            irr_table = sensitivity.pivot(
                index="annual_growth_rate", columns="exit_multiple", values="irr"
            )
            irr_table.index = [f"{value:.1%}" for value in irr_table.index]
            irr_table.columns = [f"{value:.1f}x" for value in irr_table.columns]
            st.subheader("IRR敏感性：增长假设 × 退出倍数")
            st.dataframe(irr_table.style.format("{:.1%}", na_rep="—"), width="stretch")

with sources_tab:
    st.subheader("公开来源账本")
    sources = source_ledger(scope_data)
    st.dataframe(
        sources,
        column_config={"source_url": st.column_config.LinkColumn("公开来源")},
        hide_index=True,
        width="stretch",
    )
    st.subheader("申报事实账本")
    facts = evidence_ledger(scope_data)
    st.caption("record_type=reported_fact；派生指标不写回为申报事实。")
    st.dataframe(
        facts,
        column_config={"source_url": st.column_config.LinkColumn("公开来源")},
        hide_index=True,
        width="stretch",
    )
    st.subheader("派生指标公式")
    st.dataframe(formula_catalog(), hide_index=True, width="stretch")

    report = render_research_report(
        scope_data,
        primary_ticker=ticker,
        peer_tickers=peer_tickers,
        assumptions=assumptions,
        scenario=scenario,
    )
    manifest = build_run_manifest(
        scope_data,
        input_mode=input_mode,
        start_year=start_year,
        end_year=end_year,
        primary_ticker=ticker,
        peer_tickers=peer_tickers,
        assumptions=assumptions,
    )
    download1, download2, download3 = st.columns(3)
    safe_name = "".join(character.lower() for character in ticker if character.isalnum() or character in "-_")
    download1.download_button(
        "下载Markdown报告",
        report,
        file_name=f"{safe_name}-financial-research.md",
        mime="text/markdown",
    )
    download2.download_button(
        "下载run_manifest.json",
        manifest_json(manifest),
        file_name=f"{safe_name}-run-manifest.json",
        mime="application/json",
    )
    download3.download_button(
        "下载事实账本CSV",
        facts.to_csv(index=False),
        file_name=f"{safe_name}-reported-facts.csv",
        mime="text/csv",
    )
    st.info(
        "上传内容只在当前会话内解析；报告记录事实、公式、用户假设与覆盖边界。"
        "重要结论仍需回到原始SEC申报文件核验。"
    )
