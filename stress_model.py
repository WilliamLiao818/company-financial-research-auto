"""A terminal enterprise-value comparison using reported annual revenue and explicit assumptions."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import date
from math import isfinite


PRESETS = ("Demand slows", "Margins compress", "Multiple compresses", "Combined downside")
FORMULA = "Terminal EV = reported annual revenue × (1 + annual growth)^years × terminal operating margin × EV/operating profit multiple."


@dataclass(frozen=True)
class Assumptions:
    growth: float
    margin: float
    multiple: float


@dataclass(frozen=True)
class Outcome:
    revenue: float
    operating_profit: float
    enterprise_value: float | None


def preset_cases(defaults: dict, preset: str) -> tuple[Assumptions, Assumptions]:
    if preset not in PRESETS:
        raise ValueError("Unknown stress preset.")
    base = Assumptions(defaults["base_growth"], defaults["base_margin"], 15.0)
    stress = Assumptions(
        defaults["bear_growth"] if preset in ("Demand slows", "Combined downside") else base.growth,
        defaults["bear_margin"] if preset in ("Margins compress", "Combined downside") else base.margin,
        12.0 if preset in ("Multiple compresses", "Combined downside") else base.multiple,
    )
    return base, stress


def project(revenue: float, years: int, case: Assumptions) -> Outcome:
    if not all(isfinite(value) for value in (revenue, case.growth, case.margin, case.multiple)):
        raise ValueError("The revenue anchor and all assumptions must be finite.")
    if revenue <= 0 or not 1 <= years <= 10 or int(years) != years or case.growth <= -1 or case.multiple <= 0:
        raise ValueError("Use positive reported revenue and multiple, a 1–10 year horizon and growth above −100%.")
    terminal_revenue = revenue * (1 + case.growth) ** years
    profit = terminal_revenue * case.margin
    return Outcome(terminal_revenue, profit, profit * case.multiple if profit > 0 else None)


def compare(revenue: float, years: int, base: Assumptions, stress: Assumptions) -> dict:
    reference = project(revenue, years, base)
    alternative = project(revenue, years, stress)
    result = {
        "base": asdict(reference), "stress": asdict(alternative),
        "difference": None, "relative_difference": None, "contributions": {},
    }
    if reference.enterprise_value is None or alternative.enterprise_value is None:
        return result
    growth_only = project(revenue, years, replace(base, growth=stress.growth)).enterprise_value
    growth_and_margin = project(revenue, years, replace(stress, multiple=base.multiple)).enterprise_value
    result["difference"] = alternative.enterprise_value - reference.enterprise_value
    result["relative_difference"] = result["difference"] / reference.enterprise_value
    result["contributions"] = {
        "Revenue growth": growth_only - reference.enterprise_value,
        "Operating margin": growth_and_margin - growth_only,
        "Exit multiple": alternative.enterprise_value - growth_and_margin,
    }
    return result


def case_record(summary: dict, years: int, base: Assumptions, stress: Assumptions, preset: str) -> dict:
    revenue = float(summary["revenue"])
    try:
        filed = date.fromisoformat(str(summary["filed"])[:10]).isoformat()
    except ValueError:
        filed = None
    currency = str(summary["currency"])
    currency_note = (
        "TSMC reports in TWD. This USD anchor uses the filing’s convenience translation."
        if summary["ticker"] == "TSM" and currency == "USD"
        else f"Amounts use the annual statement series currency ({currency})."
    )
    return {
        "model": "Terminal enterprise value · v1",
        "ticker": str(summary["ticker"]), "company": str(summary["company"]),
        "currency": currency, "units": "whole units in the annual statement series currency",
        "currency_basis": currency_note,
        "reported_facts": {
            "annual_revenue": revenue, "fiscal_year": int(summary["fiscal_year"]),
            "period_end": str(summary["fiscal_year_end"]), "filed": filed,
            "public_source": str(summary["source_url"]),
        },
        "starting_preset": preset, "horizon_years": years,
        "assumptions": {"base": asdict(base), "stress": asdict(stress)},
        "outputs": compare(revenue, years, base, stress),
        "formula": FORMULA,
        "method": "Growth and margin are decimal fractions. Both cases use the same revenue anchor and horizon. "
                  "Attribution replaces growth, then margin, then the multiple. Interactions are assigned in that order. "
                  "A nonpositive operating profit has no meaningful positive earnings-multiple valuation.",
    }


def scenario_note(record: dict) -> str:
    facts = record["reported_facts"]
    outputs = record["outputs"]
    currency = record["currency"]

    def amount(value: float | None) -> str:
        return "N/M" if value is None else f"{currency} {value / 1e9:,.3f} billion"

    lines = [
        f"# {record['company']} · Valuation stress test", "",
        f"{record['ticker']} · FY{facts['fiscal_year']} · {record['starting_preset']} · "
        f"{record['horizon_years']}-year horizon", "",
        f"Base terminal enterprise value is **{amount(outputs['base']['enterprise_value'])}**.  ",
        f"Stressed terminal enterprise value is **{amount(outputs['stress']['enterprise_value'])}**.  ",
        f"The change from base is **{amount(outputs['difference'])}**.", "",
        "| Assumption | Base | Stress |", "| --- | ---: | ---: |",
    ]
    values = record["assumptions"]
    for key, label, spec in (
        ("growth", "Annual growth", ".2%"),
        ("margin", "Terminal operating margin", ".2%"),
        ("multiple", "Operating-profit multiple (×)", ".2f"),
    ):
        lines.append(f"| {label} | {values['base'][key]:{spec}} | {values['stress'][key]:{spec}} |")
    lines.extend(["", "## What changed", ""])
    for label, contribution in outputs["contributions"].items():
        lines.append(f"- {label} · {amount(contribution)}")
    if not outputs["contributions"]:
        lines.append("A case has nonpositive terminal operating profit. An operating-profit multiple cannot give a meaningful EV for that case.")
    lines.extend([
        "", "## Calculation and reported input", "", record["formula"], "", record["method"], "",
        f"Reported revenue was {amount(facts['annual_revenue'])} for the period ended {facts['period_end']}. "
        f"Filing date · {facts['filed'] or 'unavailable'}. {record['currency_basis']}",
        "", f"[Open financial record]({facts['public_source']})", "",
        "## Exact inputs and outputs", "", "```json", json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False), "```", "",
    ])
    return "\n".join(lines)
