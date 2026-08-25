from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


DATA_PATH = Path(__file__).parent / "data" / "financials.csv"

SCHEMA_VERSION = "1.0.0"
FORMULA_VERSION = "1.0.0"

REPORTED_FACT_FIELDS = [
    "revenue",
    "gross_profit",
    "cost_of_revenue",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "capex",
    "assets",
    "liabilities",
    "equity",
]

REQUIRED_FINANCIAL_COLUMNS = {
    "ticker",
    "company",
    "fiscal_year",
    "fiscal_year_end",
    "filed",
    "source_url",
    *REPORTED_FACT_FIELDS,
}


FORMULA_DEFINITIONS = {
    "revenue_growth": {
        "label": "Revenue growth / 营收同比增长",
        "formula": "Revenue_t / Revenue_(t-1) - 1",
        "purpose": "Compare the latest annual revenue with the prior fiscal year.",
    },
    "gross_margin": {
        "label": "Gross margin / 毛利率",
        "formula": "Gross profit / Revenue",
        "purpose": "Observe product economics; comparability depends on company reporting tags.",
    },
    "operating_margin": {
        "label": "Operating margin / 营业利润率",
        "formula": "Operating income / Revenue",
        "purpose": "Observe operating profitability before financing and tax items.",
    },
    "net_margin": {
        "label": "Net margin / 净利率",
        "formula": "Net income / Revenue",
        "purpose": "Observe reported bottom-line profitability; one-off and financing items require filing review.",
    },
    "free_cash_flow": {
        "label": "Free cash flow / 自由现金流",
        "formula": "Operating cash flow - Capital expenditure",
        "purpose": "A simple, reproducible FCF proxy; it is not unlevered free cash flow.",
    },
    "fcf_margin": {
        "label": "FCF margin / 自由现金流率",
        "formula": "Free cash flow / Revenue",
        "purpose": "Compare simple cash generation with revenue on the same fiscal-year basis.",
    },
    "capex_intensity": {
        "label": "Capex intensity / 资本开支强度",
        "formula": "Capital expenditure / Revenue",
        "purpose": "Flag years in which reported capital expenditure is large relative to revenue.",
    },
    "cash_conversion": {
        "label": "Cash conversion / 盈利现金转化",
        "formula": "Operating cash flow / Net income",
        "purpose": "A screening prompt only; working capital and one-off items require filing review.",
    },
    "debt_to_assets_proxy": {
        "label": "Liabilities/assets proxy / 负债资产比",
        "formula": "Total liabilities / Total assets",
        "purpose": "A balance-sheet structure proxy, not net debt or a credit rating.",
    },
}


VALUATION_METRICS = {
    "revenue": {
        "label": "Revenue / 营收",
        "multiple_label": "EV / Revenue",
    },
    "operating_income": {
        "label": "Operating income / 营业利润",
        "multiple_label": "EV / Operating income",
    },
    "free_cash_flow": {
        "label": "Simple free cash flow / 简化自由现金流",
        "multiple_label": "EV / simple FCF (scenario proxy)",
    },
}


def validate_financials(frame: pd.DataFrame) -> list[str]:
    """Validate the public-research CSV contract without inventing missing fields."""
    errors: list[str] = []
    missing = REQUIRED_FINANCIAL_COLUMNS.difference(frame.columns)
    if missing:
        return ["Missing required financial columns: " + ", ".join(sorted(missing))]
    if frame.empty:
        return ["The financial dataset is empty."]
    if frame["ticker"].fillna("").astype(str).str.strip().eq("").any():
        errors.append("Every row must include a ticker or CIK-based identifier.")
    if frame["company"].fillna("").astype(str).str.strip().eq("").any():
        errors.append("Every row must include a company name.")
    fiscal_year = pd.to_numeric(frame["fiscal_year"], errors="coerce")
    if fiscal_year.isna().any():
        errors.append("Every fiscal_year must be numeric.")
    if not frame["fiscal_year_end"].fillna("").astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        errors.append("Every fiscal_year_end must use YYYY-MM-DD.")
    urls = frame["source_url"].fillna("").astype(str)
    if not urls.str.startswith(("https://", "http://")).all():
        errors.append("Every row must include an HTTP(S) public source URL.")
    if frame.duplicated(["ticker", "fiscal_year", "fiscal_year_end"]).any():
        errors.append("Duplicate ticker/fiscal_year/fiscal_year_end rows are not allowed.")
    return errors


def prepare_financials(frame: pd.DataFrame, *, input_source: str = "uploaded_csv") -> pd.DataFrame:
    errors = validate_financials(frame)
    if errors:
        raise ValueError("; ".join(errors))
    result = frame.copy()
    result["ticker"] = result["ticker"].astype(str).str.strip().str.upper()
    result["company"] = result["company"].astype(str).str.strip()
    result["fiscal_year"] = pd.to_numeric(result["fiscal_year"], errors="raise").astype(int)
    for column in REPORTED_FACT_FIELDS:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["input_source"] = input_source
    return add_metrics(result)


def load_financials(path: Path | str = DATA_PATH) -> pd.DataFrame:
    """Load the frozen SEC snapshot and calculate transparent research metrics."""
    return prepare_financials(pd.read_csv(path), input_source="frozen_demo")


def filter_year_range(frame: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    if start_year > end_year:
        raise ValueError("Start year cannot be after end year.")
    filtered = frame.loc[frame["fiscal_year"].between(start_year, end_year)].copy()
    if filtered.empty:
        raise ValueError(f"No fiscal-year rows are available between {start_year} and {end_year}.")
    return add_metrics(filtered.drop(columns=[column for column in FORMULA_DEFINITIONS if column in filtered], errors="ignore"))


def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.replace(0, pd.NA)
    return numerator / denominator


def add_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["gross_margin"] = safe_ratio(result["gross_profit"], result["revenue"])
    result["operating_margin"] = safe_ratio(result["operating_income"], result["revenue"])
    result["net_margin"] = safe_ratio(result["net_income"], result["revenue"])
    result["free_cash_flow"] = result["operating_cash_flow"] - result["capex"]
    result["fcf_margin"] = safe_ratio(result["free_cash_flow"], result["revenue"])
    result["capex_intensity"] = safe_ratio(result["capex"], result["revenue"])
    result["cash_conversion"] = safe_ratio(result["operating_cash_flow"], result["net_income"])
    result["debt_to_assets_proxy"] = safe_ratio(result["liabilities"], result["assets"])
    result = result.sort_values(["ticker", "fiscal_year"])
    result["revenue_growth"] = result.groupby("ticker")["revenue"].pct_change(fill_method=None)
    result["operating_margin_change"] = result.groupby("ticker")["operating_margin"].diff()
    result["revenue_growth_change"] = result.groupby("ticker")["revenue_growth"].diff()
    return result


def latest_company_summary(frame: pd.DataFrame, ticker: str) -> dict[str, object]:
    company = frame.loc[frame["ticker"] == ticker].sort_values("fiscal_year")
    if company.empty:
        raise ValueError(f"No data available for ticker {ticker}")
    latest = company.iloc[-1]
    prior = company.iloc[-2] if len(company) > 1 else None
    summary = {
        "company": latest["company"],
        "ticker": ticker,
        "fiscal_year": int(latest["fiscal_year"]),
        "fiscal_year_end": latest["fiscal_year_end"],
        "filed": latest.get("filed", pd.NA),
        "revenue": latest["revenue"],
        "gross_margin": latest["gross_margin"],
        "operating_margin": latest["operating_margin"],
        "net_margin": latest["net_margin"],
        "free_cash_flow": latest["free_cash_flow"],
        "fcf_margin": latest["fcf_margin"],
        "capex_intensity": latest["capex_intensity"],
        "cash_conversion": latest["cash_conversion"],
        "debt_to_assets_proxy": latest["debt_to_assets_proxy"],
        "source_url": latest["source_url"],
    }
    if prior is not None and pd.notna(prior["revenue"]):
        summary["revenue_growth"] = latest["revenue"] / prior["revenue"] - 1
    else:
        summary["revenue_growth"] = pd.NA
    return summary


def quality_flags(frame: pd.DataFrame, ticker: str) -> list[str]:
    company = frame.loc[frame["ticker"] == ticker].sort_values("fiscal_year")
    flags: list[str] = []
    if company.empty:
        return ["No company data found."]
    latest = company.iloc[-1]
    required = [
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "operating_cash_flow",
        "capex",
        "assets",
        "liabilities",
    ]
    missing = [column for column in required if column not in latest.index or pd.isna(latest[column])]
    if missing:
        flags.append("Missing latest-year fields: " + ", ".join(missing))
    if pd.notna(latest["operating_cash_flow"]) and pd.notna(latest["net_income"]):
        if latest["net_income"] > 0 and latest["operating_cash_flow"] < 0:
            flags.append("Positive net income but negative operating cash flow.")
    if pd.notna(latest["gross_margin"]) and not 0 <= latest["gross_margin"] <= 1:
        flags.append("Gross margin is outside the expected 0%-100% range.")
    return flags or ["No rule-based data quality warning for the latest fiscal year."]


def financial_health_prompts(frame: pd.DataFrame, ticker: str) -> list[str]:
    """Return explainable research prompts, not a score or investment recommendation."""
    company = frame.loc[frame["ticker"] == ticker].sort_values("fiscal_year")
    if company.empty:
        return ["No company data found."]

    latest = company.iloc[-1]
    prior = company.iloc[-2] if len(company) > 1 else None
    prompts: list[str] = []

    if pd.notna(latest["revenue_growth"]) and latest["revenue_growth"] < 0:
        prompts.append("营收同比下降：需要回到年报区分需求、价格、汇率和业务组合影响。")
    if prior is not None:
        if pd.notna(latest["revenue_growth_change"]) and latest["revenue_growth_change"] <= -0.10:
            prompts.append("营收增速较上年放缓至少10个百分点：需要核查基数与分部驱动。")
        if pd.notna(latest["operating_margin_change"]) and latest["operating_margin_change"] <= -0.05:
            prompts.append("营业利润率较上年下降至少5个百分点：需要核查成本、费用与业务组合。")

    if pd.notna(latest["free_cash_flow"]) and latest["free_cash_flow"] < 0:
        prompts.append("简化自由现金流为负：经营现金流不足以覆盖当年资本开支。")
    if pd.notna(latest["capex_intensity"]) and latest["capex_intensity"] >= 0.30:
        prompts.append("资本开支/营收达到30%或以上：需要核查扩产、云基础设施或一次性项目。")
    if (
        pd.notna(latest["cash_conversion"])
        and latest["net_income"] > 0
        and latest["cash_conversion"] < 0.80
    ):
        prompts.append("经营现金流/净利润低于0.8倍：需要核查营运资本与非现金项目。")
    if pd.notna(latest["debt_to_assets_proxy"]) and latest["debt_to_assets_proxy"] >= 0.80:
        prompts.append("总负债/总资产达到80%或以上：这是结构提示，不等同于净债务或信用结论。")
    if "equity" in latest.index and pd.notna(latest["equity"]) and latest["equity"] < 0:
        prompts.append("账面股东权益为负：需要核查回购、累计亏损和融资结构。")

    return prompts or ["当前规则未触发财务观察点；这不代表公司没有经营或估值风险。"]


def latest_peer_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one latest annual row per ticker for transparent peer screening."""
    latest = (
        frame.sort_values(["ticker", "fiscal_year"])
        .groupby("ticker", as_index=False, group_keys=False)
        .tail(1)
        .copy()
    )
    columns = [
        "ticker",
        "company",
        "fiscal_year",
        "fiscal_year_end",
        "filed",
        "revenue",
        "revenue_growth",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "free_cash_flow",
        "fcf_margin",
        "capex_intensity",
        "cash_conversion",
        "debt_to_assets_proxy",
        "source_url",
    ]
    return latest[[column for column in columns if column in latest.columns]].sort_values("ticker")


def formula_catalog() -> pd.DataFrame:
    """Return the in-app formula and interpretation reference."""
    return pd.DataFrame(
        [
            {
                "metric": definition["label"],
                "formula": definition["formula"],
                "interpretation_and_limit": definition["purpose"],
            }
            for definition in FORMULA_DEFINITIONS.values()
        ]
    )


def valuation_scenario(
    *,
    base_metric_value: float,
    metric: str,
    annual_growth_rate: float,
    holding_period_years: int,
    entry_multiple: float,
    exit_multiple: float,
    entry_net_debt: float = 0.0,
    exit_net_debt: float = 0.0,
) -> dict[str, float | str]:
    """Calculate a user-assumption valuation scenario with transparent formulas.

    Units cancel in the return calculation, so callers may use dollars or USD billions
    as long as the metric and net-debt inputs use the same unit.
    """
    if metric not in VALUATION_METRICS:
        raise ValueError(f"Unsupported valuation metric: {metric}")
    if base_metric_value <= 0:
        raise ValueError("Base metric must be positive.")
    if annual_growth_rate <= -1:
        raise ValueError("Annual growth rate must be greater than -100%.")
    if holding_period_years <= 0:
        raise ValueError("Holding period must be positive.")
    if entry_multiple <= 0 or exit_multiple <= 0:
        raise ValueError("Entry and exit multiples must be positive.")

    exit_metric_value = base_metric_value * (1 + annual_growth_rate) ** holding_period_years
    entry_enterprise_value = base_metric_value * entry_multiple
    exit_enterprise_value = exit_metric_value * exit_multiple
    entry_equity_value = entry_enterprise_value - entry_net_debt
    exit_equity_value = exit_enterprise_value - exit_net_debt
    if entry_equity_value <= 0:
        raise ValueError("Entry equity value must be positive after subtracting entry net debt.")
    if exit_equity_value <= 0:
        raise ValueError("Exit equity value must be positive after subtracting exit net debt.")

    moic = exit_equity_value / entry_equity_value
    irr = moic ** (1 / holding_period_years) - 1
    return {
        "metric": metric,
        "metric_label": VALUATION_METRICS[metric]["label"],
        "multiple_label": VALUATION_METRICS[metric]["multiple_label"],
        "base_metric_value": base_metric_value,
        "exit_metric_value": exit_metric_value,
        "entry_enterprise_value": entry_enterprise_value,
        "exit_enterprise_value": exit_enterprise_value,
        "entry_equity_value": entry_equity_value,
        "exit_equity_value": exit_equity_value,
        "moic": moic,
        "irr": irr,
    }


def scenario_sensitivity(
    *,
    base_metric_value: float,
    metric: str,
    annual_growth_rates: Iterable[float],
    holding_period_years: int,
    entry_multiple: float,
    exit_multiples: Iterable[float],
    entry_net_debt: float = 0.0,
    exit_net_debt: float = 0.0,
) -> pd.DataFrame:
    """Calculate MOIC and IRR across explicit growth and exit-multiple assumptions."""
    rows: list[dict[str, float]] = []
    for growth_rate in annual_growth_rates:
        for exit_multiple in exit_multiples:
            try:
                result = valuation_scenario(
                    base_metric_value=base_metric_value,
                    metric=metric,
                    annual_growth_rate=growth_rate,
                    holding_period_years=holding_period_years,
                    entry_multiple=entry_multiple,
                    exit_multiple=exit_multiple,
                    entry_net_debt=entry_net_debt,
                    exit_net_debt=exit_net_debt,
                )
                moic = float(result["moic"])
                irr = float(result["irr"])
            except ValueError:
                moic = float("nan")
                irr = float("nan")
            rows.append(
                {
                    "annual_growth_rate": growth_rate,
                    "exit_multiple": exit_multiple,
                    "moic": moic,
                    "irr": irr,
                }
            )
    return pd.DataFrame(rows)


def source_ledger(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one source record per company-year without fetching uploaded URLs."""
    columns = [
        "ticker",
        "company",
        "cik",
        "fiscal_year",
        "fiscal_year_end",
        "filed",
        "form",
        "accession",
        "input_source",
        "source_url",
    ]
    ledger = frame[[column for column in columns if column in frame.columns]].copy()
    return ledger.drop_duplicates().sort_values(["ticker", "fiscal_year"]).reset_index(drop=True)


def evidence_ledger(frame: pd.DataFrame) -> pd.DataFrame:
    """Separate reported facts from derived metrics and preserve metric-level SEC provenance when present."""
    rows: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        values = row._asdict()
        for field in REPORTED_FACT_FIELDS:
            value = values.get(field)
            if pd.isna(value):
                continue
            rows.append(
                {
                    "ticker": values.get("ticker"),
                    "company": values.get("company"),
                    "fiscal_year": values.get("fiscal_year"),
                    "fiscal_year_end": values.get("fiscal_year_end"),
                    "record_type": "reported_fact",
                    "field": field,
                    "value": value,
                    "unit": "USD",
                    "xbrl_tag": values.get(f"{field}_xbrl_tag", ""),
                    "accession": values.get(f"{field}_accession", values.get("accession", "")),
                    "filed": values.get("filed", ""),
                    "source_url": values.get("source_url", ""),
                }
            )
    return pd.DataFrame(rows)


def assumption_ledger(assumptions: Mapping[str, object] | None) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "name": name,
                "value": str(value),
                "record_type": "user_assumption",
                "source": "user_input",
            }
            for name, value in (assumptions or {}).items()
        ]
    )


def _markdown_text(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _percent(value: object) -> str:
    return "—" if value is None or pd.isna(value) else f"{float(value):.1%}"


def _money(value: object) -> str:
    return "—" if value is None or pd.isna(value) else f"${float(value) / 1e9:,.1f}B"


def render_research_report(
    frame: pd.DataFrame,
    *,
    primary_ticker: str,
    peer_tickers: Iterable[str],
    assumptions: Mapping[str, object] | None = None,
    scenario: Mapping[str, object] | None = None,
) -> str:
    peers = list(dict.fromkeys([primary_ticker, *peer_tickers]))
    scoped = frame.loc[frame["ticker"].isin(peers)].copy()
    if scoped.empty or primary_ticker not in set(scoped["ticker"]):
        raise ValueError(f"No data available for primary ticker {primary_ticker}.")
    summary = latest_company_summary(scoped, primary_ticker)
    comparison = latest_peer_comparison(scoped)
    sources = source_ledger(scoped)
    primary = scoped.loc[scoped["ticker"] == primary_ticker].sort_values("fiscal_year")

    lines = [
        f"# Company financial research report: {_markdown_text(summary['company'])}",
        "",
        "> Public-source research aid. Reported facts, deterministic derived metrics and user assumptions are separated below. Not investment advice.",
        "",
        "## Scope",
        "",
        f"- Primary identifier: `{_markdown_text(primary_ticker)}`",
        f"- Fiscal years: {int(primary['fiscal_year'].min())}–{int(primary['fiscal_year'].max())}",
        f"- User-selected comparison set: {', '.join(f'`{_markdown_text(item)}`' for item in peers)}",
        "",
        "## Reported facts",
        "",
        "| Fiscal year | Revenue | Operating income | Net income | Operating cash flow | Capex | Source |",
        "|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in primary.itertuples(index=False):
        lines.append(
            f"| {row.fiscal_year} | {_money(row.revenue)} | {_money(row.operating_income)} | "
            f"{_money(row.net_income)} | {_money(row.operating_cash_flow)} | {_money(row.capex)} | "
            f"[SEC/public source]({_markdown_text(row.source_url)}) |"
        )

    lines.extend(
        [
            "",
            "## Deterministic derived metrics",
            "",
            "| Ticker | FY end | Revenue growth | Gross margin | Operating margin | FCF margin | Capex intensity |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in comparison.itertuples(index=False):
        lines.append(
            f"| {_markdown_text(row.ticker)} | {_markdown_text(row.fiscal_year_end)} | "
            f"{_percent(row.revenue_growth)} | {_percent(row.gross_margin)} | "
            f"{_percent(row.operating_margin)} | {_percent(row.fcf_margin)} | {_percent(row.capex_intensity)} |"
        )
    lines.extend(["", "Formulas are deterministic and listed in the application formula catalog."])

    lines.extend(["", "## User assumptions", ""])
    if assumptions:
        for name, value in assumptions.items():
            lines.append(f"- **{_markdown_text(name)}:** {_markdown_text(value)}")
    else:
        lines.append("- No valuation/return assumptions were supplied for this report.")

    lines.extend(["", "## Scenario result", ""])
    if scenario:
        lines.extend(
            [
                f"- Entry equity value: ${float(scenario['entry_equity_value']):,.2f}B",
                f"- Exit equity value: ${float(scenario['exit_equity_value']):,.2f}B",
                f"- MOIC: {float(scenario['moic']):.2f}x",
                f"- IRR: {float(scenario['irr']):.1%}",
            ]
        )
    else:
        lines.append("- No valid scenario was calculated.")

    lines.extend(["", "## Source ledger", "", "| Ticker | FY end | Filed | Accession | Source |", "|---|---|---|---|---|"])
    for row in sources.itertuples(index=False):
        values = row._asdict()
        lines.append(
            f"| {_markdown_text(values.get('ticker', ''))} | {_markdown_text(values.get('fiscal_year_end', ''))} | "
            f"{_markdown_text(values.get('filed', ''))} | {_markdown_text(values.get('accession', '')) or '—'} | "
            f"[open source]({_markdown_text(values.get('source_url', ''))}) |"
        )

    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- The tool supports public U.S. SEC Company Facts and a documented same-schema CSV; it does not claim global-company coverage.",
            "- Missing or incompatible XBRL facts remain missing and must be checked against the original filing.",
            "- User-selected companies are not automatically validated as strict valuation comparables.",
            "- Scenario outputs are assumption-driven teaching calculations, not a DCF, target price or investment recommendation.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_run_manifest(
    frame: pd.DataFrame,
    *,
    input_mode: str,
    start_year: int,
    end_year: int,
    primary_ticker: str,
    peer_tickers: Iterable[str],
    assumptions: Mapping[str, object] | None = None,
    generated_at: str | None = None,
) -> dict[str, object]:
    input_columns = [
        column
        for column in frame.columns
        if column in REQUIRED_FINANCIAL_COLUMNS
        or column
        in {
            "cik",
            "form",
            "accession",
            "input_source",
        }
        or column.endswith("_xbrl_tag")
        or column.endswith("_accession")
    ]
    canonical = (
        frame[input_columns]
        .sort_values(["ticker", "fiscal_year", "fiscal_year_end"])
        .to_csv(index=False)
    )
    sources = sorted(set(frame["source_url"].dropna().astype(str)))
    return {
        "schema_version": SCHEMA_VERSION,
        "formula_version": FORMULA_VERSION,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "input_mode": input_mode,
        "year_range": {"start": start_year, "end": end_year},
        "primary_ticker": primary_ticker,
        "peer_tickers": list(dict.fromkeys(peer_tickers)),
        "record_count": int(len(frame)),
        "tickers": sorted(frame["ticker"].unique().tolist()),
        "source_urls": sources,
        "reported_fact_fields": REPORTED_FACT_FIELDS,
        "derived_metrics": list(FORMULA_DEFINITIONS),
        "user_assumptions": dict(assumptions or {}),
        "input_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "uploads_persisted": False,
        "coverage_boundary": "Public U.S. SEC Company Facts or same-schema uploaded CSV only",
        "warning": "Missing data is not guessed; outputs are not investment advice.",
    }


def manifest_json(manifest: Mapping[str, object]) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n"
