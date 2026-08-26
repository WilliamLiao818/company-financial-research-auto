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
AUDIT_VERSION = "1.0.0"
FISCAL_YEAR_END_ALIGNMENT_DAYS = 31

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

SOURCE_FILING_METADATA_FIELDS = ["source_url", "filed"]
FILING_IDENTITY_FIELDS = ["form", "accession"]
REVIEW_QUEUE_COLUMNS = [
    "issue_type",
    "ticker",
    "company",
    "fiscal_year",
    "field",
    "observed_or_missing",
    "audit_rule",
    "next_check",
]

AUDIT_DEFINITIONS = {
    "core_fact_completeness": {
        "label": "Core reported-fact completeness / 核心申报事实完整度",
        "formula": "non-null cells across 10 core reported-fact fields / (company-year rows × 10)",
        "threshold": "No pass/fail threshold; every null creates a review-queue item.",
        "meaning": "Measures observed fact coverage only; it does not assess company quality.",
    },
    "source_filing_metadata_coverage": {
        "label": "Source and filing metadata coverage / 来源与申报元数据覆盖",
        "formula": "non-blank source_url and filed cells / (company-year rows × 2)",
        "threshold": "A blank cell is a review item; no quality score is assigned.",
        "meaning": "Measures whether each company-year can be traced to a dated public source.",
    },
    "filing_identity_coverage": {
        "label": "Filing identity coverage / 申报身份元数据覆盖",
        "formula": "non-blank form and accession cells / (company-year rows × 2)",
        "threshold": "A blank cell is a review item; CSV inputs may legitimately lack these optional fields.",
        "meaning": "Shows whether the filing form and accession are available for precise retrieval.",
    },
    "fact_provenance_coverage": {
        "label": "Fact-level provenance coverage / 事实级溯源覆盖",
        "formula": "non-blank XBRL tag and fact accession cells / (observed core facts × 2)",
        "threshold": "A missing component is a review item; the reported value is not discarded or guessed.",
        "meaning": "Shows how much of the fact ledger can be traced below the company-year source level.",
    },
    "peer_annual_comparability_coverage": {
        "label": "Peer annual overlap / 比较公司年度重叠覆盖",
        "formula": "fiscal years present for every selected company / fiscal years present for any selected company",
        "threshold": "Requires at least 2 selected companies; missing company-years enter the review queue.",
        "meaning": "Measures calendar-year overlap only; it does not declare companies economically comparable.",
    },
    "peer_fye_alignment_coverage": {
        "label": "Shared-year fiscal-end alignment / 共同年度财年截止日对齐覆盖",
        "formula": "shared fiscal years with max fiscal-year-end gap ≤ 31 days / all shared fiscal years",
        "threshold": "31 calendar days; wider gaps create review items for each affected company-year.",
        "meaning": "Flags calendar mismatch without judging accounting or business-model comparability.",
    },
    "user_assumption_count": {
        "label": "Explicit user assumptions / 显式用户假设数量",
        "formula": "count of non-empty entries in the user-assumption mapping",
        "threshold": "No threshold; the count is disclosed, not scored.",
        "meaning": "Keeps scenario choices visible and separate from reported facts.",
    },
}

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
        prompts.append("Revenue declined year over year: separate demand, pricing, foreign exchange and business-mix effects in the filing.")
    if prior is not None:
        if pd.notna(latest["revenue_growth_change"]) and latest["revenue_growth_change"] <= -0.10:
            prompts.append("Revenue growth slowed by at least 10 percentage points: review the comparison base and segment drivers.")
        if pd.notna(latest["operating_margin_change"]) and latest["operating_margin_change"] <= -0.05:
            prompts.append("Operating margin declined by at least 5 percentage points: review costs, expenses and business mix.")

    if pd.notna(latest["free_cash_flow"]) and latest["free_cash_flow"] < 0:
        prompts.append("Simple free cash flow is negative: operating cash flow did not cover reported capital expenditure.")
    if pd.notna(latest["capex_intensity"]) and latest["capex_intensity"] >= 0.30:
        prompts.append("Capex reached at least 30% of revenue: review capacity expansion, cloud infrastructure and non-recurring projects.")
    if (
        pd.notna(latest["cash_conversion"])
        and latest["net_income"] > 0
        and latest["cash_conversion"] < 0.80
    ):
        prompts.append("Operating cash flow / net income is below 0.8x: review working capital and non-cash items.")
    if pd.notna(latest["debt_to_assets_proxy"]) and latest["debt_to_assets_proxy"] >= 0.80:
        prompts.append("Total liabilities / assets reached at least 80%: this is a structure signal, not a net-debt or credit conclusion.")
    if "equity" in latest.index and pd.notna(latest["equity"]) and latest["equity"] < 0:
        prompts.append("Reported equity is negative: review repurchases, accumulated results and financing structure.")

    return prompts or ["No deterministic financial prompt was triggered; this does not establish an absence of operating or valuation risk."]


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


def audit_definition_catalog() -> pd.DataFrame:
    """Return every deterministic audit formula and review threshold."""
    return pd.DataFrame(
        [
            {
                "metric": metric,
                "label": definition["label"],
                "formula": definition["formula"],
                "threshold_or_queue_rule": definition["threshold"],
                "interpretation_limit": definition["meaning"],
            }
            for metric, definition in AUDIT_DEFINITIONS.items()
        ]
    )


def _present_mask(frame: pd.DataFrame, column: str) -> pd.Series:
    """Treat numeric zero as present while treating nulls and blank strings as absent."""
    if column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    values = frame[column]
    return values.notna() & values.astype("string").str.strip().ne("").fillna(False)


def _assumption_is_present(value: object) -> bool:
    if value is None or (isinstance(value, str) and not value.strip()):
        return False
    try:
        return not bool(pd.isna(value))
    except (TypeError, ValueError):
        return True


def review_queue(
    frame: pd.DataFrame,
    *,
    fiscal_year_end_alignment_days: int = FISCAL_YEAR_END_ALIGNMENT_DAYS,
) -> pd.DataFrame:
    """List deterministic missingness and comparability checks without imputing values."""
    if fiscal_year_end_alignment_days < 0:
        raise ValueError("Fiscal-year-end alignment days cannot be negative.")
    if frame.empty:
        return pd.DataFrame(columns=REVIEW_QUEUE_COLUMNS)

    rows: list[dict[str, object]] = []
    ordered = frame.sort_values(["ticker", "fiscal_year", "fiscal_year_end"])

    def add_issue(
        values: Mapping[str, object],
        *,
        issue_type: str,
        field: str,
        observed_or_missing: str,
        audit_rule: str,
        next_check: str,
    ) -> None:
        rows.append(
            {
                "issue_type": issue_type,
                "ticker": values.get("ticker", ""),
                "company": values.get("company", ""),
                "fiscal_year": values.get("fiscal_year", ""),
                "field": field,
                "observed_or_missing": observed_or_missing,
                "audit_rule": audit_rule,
                "next_check": next_check,
            }
        )

    for _, row in ordered.iterrows():
        values = row.to_dict()
        for field in REPORTED_FACT_FIELDS:
            if field not in row.index or pd.isna(row[field]):
                add_issue(
                    values,
                    issue_type="missing_reported_fact",
                    field=field,
                    observed_or_missing="missing",
                    audit_rule="Core fact is null for this company-year.",
                    next_check="Check the original filing and supported XBRL tags; keep null until verified.",
                )

        for field in SOURCE_FILING_METADATA_FIELDS:
            value = values.get(field)
            if value is None or pd.isna(value) or not str(value).strip():
                add_issue(
                    values,
                    issue_type="missing_source_filing_metadata",
                    field=field,
                    observed_or_missing="missing",
                    audit_rule="source_url and filed are expected for every company-year.",
                    next_check="Locate the dated public filing source; do not infer the missing metadata.",
                )

        for field in FILING_IDENTITY_FIELDS:
            value = values.get(field)
            if value is None or pd.isna(value) or not str(value).strip():
                add_issue(
                    values,
                    issue_type="missing_filing_identity",
                    field=field,
                    observed_or_missing="missing",
                    audit_rule="Filing form and accession are checked when available.",
                    next_check="Confirm the form/accession in the original filing or retain the documented gap.",
                )

        fiscal_year_end = pd.to_datetime(values.get("fiscal_year_end"), errors="coerce")
        if pd.isna(fiscal_year_end):
            add_issue(
                values,
                issue_type="invalid_fiscal_year_end",
                field="fiscal_year_end",
                observed_or_missing=str(values.get("fiscal_year_end", "missing")),
                audit_rule="fiscal_year_end must be a valid calendar date.",
                next_check="Verify the fiscal-year-end date against the filing.",
            )

        for field in REPORTED_FACT_FIELDS:
            value = values.get(field)
            if value is None or pd.isna(value):
                continue
            missing_components: list[str] = []
            for component in (f"{field}_xbrl_tag", f"{field}_accession"):
                component_value = values.get(component)
                if component_value is None or pd.isna(component_value) or not str(component_value).strip():
                    missing_components.append(component)
            if missing_components:
                add_issue(
                    values,
                    issue_type="missing_fact_provenance",
                    field=field,
                    observed_or_missing=", ".join(missing_components),
                    audit_rule="Each observed fact is checked for an XBRL tag and fact accession.",
                    next_check="Trace the value to the original filing; do not treat absent provenance as a new fact.",
                )

    tickers = sorted(ordered["ticker"].dropna().astype(str).unique())
    if len(tickers) >= 2:
        ticker_years = {
            ticker: set(
                pd.to_numeric(
                    ordered.loc[ordered["ticker"].astype(str) == ticker, "fiscal_year"],
                    errors="coerce",
                )
                .dropna()
                .astype(int)
            )
            for ticker in tickers
        }
        all_years = sorted(set().union(*ticker_years.values()))
        company_by_ticker = (
            ordered.drop_duplicates("ticker").set_index("ticker")["company"].astype(str).to_dict()
        )
        for fiscal_year in all_years:
            for ticker in tickers:
                if fiscal_year not in ticker_years[ticker]:
                    add_issue(
                        {
                            "ticker": ticker,
                            "company": company_by_ticker.get(ticker, ""),
                            "fiscal_year": fiscal_year,
                        },
                        issue_type="missing_peer_year",
                        field="company_year_row",
                        observed_or_missing="missing",
                        audit_rule="Every selected company must have a row for a year to count as shared coverage.",
                        next_check="Add a verified company-year row or exclude that year from like-for-like comparison.",
                    )

        shared_years = sorted(set.intersection(*ticker_years.values())) if ticker_years else []
        for fiscal_year in shared_years:
            shared = ordered.loc[
                ordered["ticker"].astype(str).isin(tickers)
                & (pd.to_numeric(ordered["fiscal_year"], errors="coerce") == fiscal_year)
            ].copy()
            shared["_parsed_fiscal_year_end"] = pd.to_datetime(
                shared["fiscal_year_end"], errors="coerce"
            )
            valid_dates = shared["_parsed_fiscal_year_end"].dropna()
            if len(valid_dates) != len(tickers):
                continue
            gap_days = int((valid_dates.max() - valid_dates.min()).days)
            if gap_days > fiscal_year_end_alignment_days:
                for _, row in shared.sort_values("ticker").iterrows():
                    add_issue(
                        row.to_dict(),
                        issue_type="fiscal_year_end_misalignment",
                        field="fiscal_year_end",
                        observed_or_missing=str(row["fiscal_year_end"]),
                        audit_rule=(
                            f"Max fiscal-year-end gap is {gap_days} days; "
                            f"alignment threshold is {fiscal_year_end_alignment_days} days."
                        ),
                        next_check="Normalize period context or avoid treating the shared fiscal year as fully aligned.",
                    )

    queue = pd.DataFrame(rows, columns=REVIEW_QUEUE_COLUMNS)
    if queue.empty:
        return queue
    return queue.sort_values(
        ["issue_type", "ticker", "fiscal_year", "field"], kind="stable"
    ).reset_index(drop=True)


def build_research_audit(
    frame: pd.DataFrame,
    *,
    assumptions: Mapping[str, object] | None = None,
    fiscal_year_end_alignment_days: int = FISCAL_YEAR_END_ALIGNMENT_DAYS,
) -> dict[str, object]:
    """Quantify research coverage; the result is an audit record, not a rating."""
    queue = review_queue(
        frame, fiscal_year_end_alignment_days=fiscal_year_end_alignment_days
    )
    row_count = int(len(frame))

    core_denominator = row_count * len(REPORTED_FACT_FIELDS)
    core_numerator = int(sum(int(_present_mask(frame, field).sum()) for field in REPORTED_FACT_FIELDS))

    source_denominator = row_count * len(SOURCE_FILING_METADATA_FIELDS)
    source_numerator = int(
        sum(int(_present_mask(frame, field).sum()) for field in SOURCE_FILING_METADATA_FIELDS)
    )

    identity_denominator = row_count * len(FILING_IDENTITY_FIELDS)
    identity_numerator = int(
        sum(int(_present_mask(frame, field).sum()) for field in FILING_IDENTITY_FIELDS)
    )

    observed_facts = 0
    fact_provenance_numerator = 0
    for field in REPORTED_FACT_FIELDS:
        observed_mask = _present_mask(frame, field)
        observed_facts += int(observed_mask.sum())
        fact_provenance_numerator += int((_present_mask(frame, f"{field}_xbrl_tag") & observed_mask).sum())
        fact_provenance_numerator += int((_present_mask(frame, f"{field}_accession") & observed_mask).sum())
    fact_provenance_denominator = observed_facts * 2

    tickers = sorted(frame["ticker"].dropna().astype(str).unique()) if "ticker" in frame else []
    annual_numerator = 0
    annual_denominator = 0
    shared_years: list[int] = []
    if len(tickers) >= 2:
        ticker_years = {
            ticker: set(
                pd.to_numeric(
                    frame.loc[frame["ticker"].astype(str) == ticker, "fiscal_year"],
                    errors="coerce",
                )
                .dropna()
                .astype(int)
            )
            for ticker in tickers
        }
        union_years = set().union(*ticker_years.values())
        shared_years = sorted(set.intersection(*ticker_years.values()))
        annual_numerator = len(shared_years)
        annual_denominator = len(union_years)

    aligned_years = 0
    alignment_denominator = 0
    if len(tickers) >= 2:
        for fiscal_year in shared_years:
            dates = pd.to_datetime(
                frame.loc[
                    frame["ticker"].astype(str).isin(tickers)
                    & (pd.to_numeric(frame["fiscal_year"], errors="coerce") == fiscal_year),
                    "fiscal_year_end",
                ],
                errors="coerce",
            ).dropna()
            alignment_denominator += 1
            if len(dates) == len(tickers) and int((dates.max() - dates.min()).days) <= fiscal_year_end_alignment_days:
                aligned_years += 1

    assumption_count = sum(
        1 for value in (assumptions or {}).values() if _assumption_is_present(value)
    )

    def coverage_metric(metric: str, numerator: int, denominator: int) -> dict[str, object]:
        definition = AUDIT_DEFINITIONS[metric]
        return {
            "label": definition["label"],
            "numerator": int(numerator),
            "denominator": int(denominator),
            "ratio": float(numerator / denominator) if denominator else None,
            "formula": definition["formula"],
            "threshold": definition["threshold"],
            "interpretation_limit": definition["meaning"],
        }

    metrics = {
        "core_fact_completeness": coverage_metric(
            "core_fact_completeness", core_numerator, core_denominator
        ),
        "source_filing_metadata_coverage": coverage_metric(
            "source_filing_metadata_coverage", source_numerator, source_denominator
        ),
        "filing_identity_coverage": coverage_metric(
            "filing_identity_coverage", identity_numerator, identity_denominator
        ),
        "fact_provenance_coverage": coverage_metric(
            "fact_provenance_coverage",
            fact_provenance_numerator,
            fact_provenance_denominator,
        ),
        "peer_annual_comparability_coverage": coverage_metric(
            "peer_annual_comparability_coverage", annual_numerator, annual_denominator
        ),
        "peer_fye_alignment_coverage": coverage_metric(
            "peer_fye_alignment_coverage", aligned_years, alignment_denominator
        ),
        "user_assumption_count": {
            "label": AUDIT_DEFINITIONS["user_assumption_count"]["label"],
            "value": int(assumption_count),
            "formula": AUDIT_DEFINITIONS["user_assumption_count"]["formula"],
            "threshold": AUDIT_DEFINITIONS["user_assumption_count"]["threshold"],
            "interpretation_limit": AUDIT_DEFINITIONS["user_assumption_count"]["meaning"],
        },
    }
    issue_counts = {
        str(issue_type): int(count)
        for issue_type, count in queue["issue_type"].value_counts().sort_index().items()
    }
    return {
        "audit_version": AUDIT_VERSION,
        "audit_kind": "deterministic_coverage_audit_not_an_investment_rating",
        "scope": {
            "company_year_rows": row_count,
            "tickers": tickers,
            "core_reported_fact_fields": list(REPORTED_FACT_FIELDS),
        },
        "parameters": {
            "fiscal_year_end_alignment_days": fiscal_year_end_alignment_days,
        },
        "metrics": metrics,
        "review_queue_count": int(len(queue)),
        "review_queue_by_issue_type": issue_counts,
    }


def audit_metrics_frame(audit: Mapping[str, object]) -> pd.DataFrame:
    """Flatten an audit record for display without dropping formulas or limits."""
    rows: list[dict[str, object]] = []
    for metric, payload in audit.get("metrics", {}).items():
        values = dict(payload)
        ratio = values.get("ratio")
        value = values.get("value") if "value" in values else ratio
        rows.append(
            {
                "metric": metric,
                "label": values.get("label", metric),
                "value": value,
                "numerator": values.get("numerator", ""),
                "denominator": values.get("denominator", ""),
                "formula": values.get("formula", ""),
                "threshold_or_queue_rule": values.get("threshold", ""),
                "interpretation_limit": values.get("interpretation_limit", ""),
            }
        )
    return pd.DataFrame(rows)


def audit_json(
    audit: Mapping[str, object],
    queue: pd.DataFrame | None = None,
) -> str:
    payload = dict(audit)
    if queue is not None:
        payload["review_queue"] = queue.where(pd.notna(queue), None).to_dict(orient="records")
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n"


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
    audit = build_research_audit(scoped, assumptions=assumptions)
    queue = review_queue(scoped)

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
            "## Deterministic research audit",
            "",
            "> Coverage measures describe the evidence in this run. They are not company-quality or investment ratings.",
            "",
            "| Audit measure | Result | Numerator | Denominator | Formula / rule |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for metric, payload in audit["metrics"].items():
        if metric == "user_assumption_count":
            result = str(payload["value"])
            numerator = "—"
            denominator = "—"
        else:
            ratio = payload["ratio"]
            result = "N/A" if ratio is None else f"{float(ratio):.1%}"
            numerator = str(payload["numerator"])
            denominator = str(payload["denominator"])
        lines.append(
            f"| {_markdown_text(payload['label'])} | {result} | {numerator} | {denominator} | "
            f"{_markdown_text(payload['formula'])}; {_markdown_text(payload['threshold'])} |"
        )

    lines.extend(
        [
            "",
            "## Review queue",
            "",
            f"- Open deterministic review items: {audit['review_queue_count']}",
        ]
    )
    if audit["review_queue_by_issue_type"]:
        for issue_type, count in audit["review_queue_by_issue_type"].items():
            lines.append(f"- `{_markdown_text(issue_type)}`: {count}")
    if queue.empty:
        lines.extend(["", "No review-queue item was generated under the published audit rules."])
    else:
        lines.extend(
            [
                "",
                "| Issue | Ticker | Fiscal year | Field | Missing / observed | Required review |",
                "|---|---|---:|---|---|---|",
            ]
        )
        for row in queue.itertuples(index=False):
            lines.append(
                f"| {_markdown_text(row.issue_type)} | {_markdown_text(row.ticker)} | "
                f"{_markdown_text(row.fiscal_year)} | {_markdown_text(row.field)} | "
                f"{_markdown_text(row.observed_or_missing)} | {_markdown_text(row.next_check)} |"
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
    audit = build_research_audit(frame, assumptions=assumptions)
    queue = review_queue(frame)
    queue_canonical = queue.to_csv(index=False)
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
        "research_audit": audit,
        "review_queue": {
            "record_count": int(len(queue)),
            "issue_counts": audit["review_queue_by_issue_type"],
            "sha256": hashlib.sha256(queue_canonical.encode("utf-8")).hexdigest(),
        },
        "input_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "uploads_persisted": False,
        "coverage_boundary": "Public U.S. SEC Company Facts or same-schema uploaded CSV only",
        "warning": "Missing data is not guessed; outputs are not investment advice.",
    }


def manifest_json(manifest: Mapping[str, object]) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n"
