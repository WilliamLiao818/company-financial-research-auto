import pandas as pd
import plotly.express as px
import streamlit as st

from research import (
    VALUATION_METRICS,
    financial_health_prompts,
    formula_catalog,
    latest_company_summary,
    latest_peer_comparison,
    load_financials,
    quality_flags,
    scenario_sensitivity,
    valuation_scenario,
)


st.set_page_config(page_title="Company Financial Research Auto", page_icon="📊", layout="wide")
st.title("Company Financial Research Auto")
st.caption(
    "基于公开SEC年度数据的可追溯财务趋势、示例公司比较和用户假设情景。"
    "本工具不提供投资建议。"
)


def percent(value) -> str:
    return "—" if value is None or pd.isna(value) else f"{value:.1%}"


def usd_billions(value) -> str:
    return "—" if value is None or pd.isna(value) else f"${value / 1e9:,.1f}B"


data = load_financials()
ticker = st.sidebar.selectbox("示例公司", sorted(data["ticker"].unique()))
st.sidebar.caption("冻结示例数据覆盖 Microsoft、Oracle 和 NVIDIA，不代表支持任意公司。")
company = data.loc[data["ticker"] == ticker].sort_values("fiscal_year")
latest = company.iloc[-1]
summary = latest_company_summary(data, ticker)

overview_tab, peers_tab, scenario_tab, sources_tab = st.tabs(
    [
        "1. 财务趋势与提示",
        "2. 最新年度同业比较",
        "3. 估值与回报情景",
        "4. 来源、公式与边界",
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
        for item in financial_health_prompts(data, ticker):
            st.write(f"- {item}")
    with right:
        st.subheader("数据质量检查")
        for item in quality_flags(data, ticker):
            st.write(f"- {item}")

with peers_tab:
    st.info(
        "三家公司财年截止日和业务结构不同。本表只比较各自最新已申报年度，"
        "不是严格可比公司估值组。"
    )
    peers = latest_peer_comparison(data)
    peer_columns = [
        "ticker",
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
        "这是教学情景，不是实时市场估值、DCF或真实交易复刻。公开数据只提供基期指标，"
        "其余假设均由用户输入。"
    )
    available_metrics = [
        name
        for name in VALUATION_METRICS
        if name in latest.index and pd.notna(latest[name]) and latest[name] > 0
    ]
    metric = st.selectbox(
        "估值基准指标",
        available_metrics,
        format_func=lambda name: VALUATION_METRICS[name]["label"],
    )
    base_value = float(latest[metric] / 1e9)
    st.metric("公开数据基期指标", f"${base_value:,.1f}B")

    col1, col2, col3 = st.columns(3)
    years = int(col1.number_input("持有期（年）", 1, 10, 5, 1))
    growth_pct = col2.number_input("指标年增长假设（%）", -50.0, 100.0, 10.0, 1.0)
    entry_multiple = col3.number_input("进场倍数", min_value=0.1, value=10.0, step=0.5)
    col4, col5, col6 = st.columns(3)
    exit_multiple = col4.number_input("退出倍数", min_value=0.1, value=10.0, step=0.5)
    entry_net_debt = col5.number_input("进场净债务（USD B）", value=0.0, step=1.0)
    exit_net_debt = col6.number_input("退出净债务（USD B）", value=0.0, step=1.0)
    growth_rate = growth_pct / 100

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
        st.error(f"当前假设无法计算：{error}")
        scenario = None

    if scenario:
        result1, result2, result3, result4 = st.columns(4)
        result1.metric("进场股权价值", f"${scenario['entry_equity_value']:,.1f}B")
        result2.metric("退出股权价值", f"${scenario['exit_equity_value']:,.1f}B")
        result3.metric("MOIC", f"{scenario['moic']:.2f}x")
        result4.metric("IRR", f"{scenario['irr']:.1%}")

        with st.expander("计算公式与未覆盖项目"):
            st.markdown(
                """
                - Exit metric = Base metric × (1 + growth rate) ^ holding years
                - Enterprise value = Metric × multiple
                - Equity value = Enterprise value - net debt
                - MOIC = Exit equity value / Entry equity value
                - IRR = MOIC ^ (1 / holding years) - 1

                未计入分红、稀释、税、交易费用、优先权、复杂债务或追加投资。
                """
            )

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
    st.subheader("数据来源")
    st.dataframe(
        latest_peer_comparison(data)[["ticker", "fiscal_year_end", "filed", "source_url"]],
        column_config={"source_url": st.column_config.LinkColumn("SEC Company Facts")},
        hide_index=True,
        width="stretch",
    )
    st.subheader("派生指标公式")
    st.dataframe(formula_catalog(), hide_index=True, width="stretch")
    st.info(
        "冻结示例仅覆盖三个预设公司。当前版本没有任意公司输入、文件上传、实时价格、"
        "自动目标价或投资建议功能；重要结论必须回到原始申报文件核验。"
    )
