"""Build the public, self-contained Lite company feed from the same inputs used by Pro."""
from __future__ import annotations

import csv
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from company_profiles import profile_for
from data_health import DATA, latest_filing, read_json
from focus_coverage import COMPANY_ROLES, COMPANY_SECTORS
from market_data import SNAPSHOT_PATH
from news_connector import load_company_news_snapshot
from research import latest_company_summary, load_financials
from research_catalog import COMPANY_NAMES, EXPANDED_PEERS, latest_results_snapshot
from stress_model import PRESETS, case_record, preset_cases


def finite_number(value) -> float | None:
    if pd.isna(value):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def latest_adjusted_closes(path: Path, as_of: date) -> dict:
    """Use the actual session recorded for each US listing, independently of its benchmarks."""
    closes = {}
    if not path.exists():
        return closes
    with path.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            ticker = row.get("series")
            if ticker not in COMPANY_NAMES:
                continue
            try:
                session = date.fromisoformat(row.get("observation_date") or "")
                value = float(row.get("adjusted_close") or "")
            except ValueError:
                continue
            if not math.isfinite(value) or value <= 0 or session > as_of:
                continue
            if session.replace(day=1).isoformat() != row.get("date"):
                continue
            observed = session.isoformat()
            if ticker not in closes or observed > closes[ticker]["observation_date"]:
                closes[ticker] = {"value": value, "currency": "USD", "observation_date": observed}
    return closes


def export_story(story: dict) -> dict:
    public = {key: story[key] for key in ("title", "publisher", "date", "url")}
    image = story.get("image", "")
    if story.get("image_kind") == "article" and image:
        parts = urlsplit(image)
        host = (parts.hostname or "").casefold()
        # Older snapshots also assigned this kind to search thumbnails and tracking pixels.
        excluded = ("bing.com", "bing.net", "matomo.cloud", "googletagmanager.com")
        if parts.scheme == "https" and host and not any(host == domain or host.endswith("." + domain) for domain in excluded):
            public["image"] = image
    return public


def build_lite_feed() -> dict:
    frame = load_financials()
    ledger = read_json(DATA / "refresh_status.json")
    source_time = ledger.get("generated_at")
    generated_at = datetime.fromisoformat(source_time).astimezone(timezone.utc) if source_time else datetime.now(timezone.utc)
    closes = latest_adjusted_closes(SNAPSHOT_PATH, generated_at.date())
    companies = {}
    for ticker in sorted(COMPANY_NAMES):
        summary = latest_company_summary(frame, ticker)
        profile = profile_for(ticker)
        revenue = finite_number(summary["revenue"])
        cases = {}
        if revenue is not None and revenue > 0:
            defaults = profile["scenario_defaults"]
            for preset in PRESETS:
                base, stress = preset_cases(defaults, preset)
                cases[preset] = case_record(summary, defaults["years"], base, stress, preset)
        quarter = latest_results_snapshot(ticker)
        quarterly_data = None
        if quarter["url"] and quarter["period_end"]:
            quarterly_data = {key: quarter.get(key) for key in (
                "label", "period_start", "period_end", "form", "filed", "currency", "unit", "url", "note",
            )}
            quarterly_data["source_kind"] = quarter.get("source_kind", "filing")
            quarterly_data["period_precision"] = quarter.get("period_precision", "day")
            quarterly_data.update({key: finite_number(quarter.get(key)) for key in ("revenue", "operating_income", "net_income")})
        filing = latest_filing(ticker)
        annual = {
            "fiscal_year": int(summary["fiscal_year"]), "period_end": str(summary["fiscal_year_end"]),
            "filed": str(summary["filed"]) if pd.notna(summary["filed"]) and summary["filed"] else None,
            "source_url": str(summary["source_url"]), "currency": str(summary["currency"]),
            "currency_basis": (
                cases[PRESETS[0]]["currency_basis"] if cases else f"Amounts use the annual statement series currency ({summary['currency']})."
            ),
            **{key: finite_number(summary[key]) for key in ("revenue", "revenue_growth", "operating_margin", "free_cash_flow")},
        }
        stories = load_company_news_snapshot(ticker, limit=3, now=generated_at)
        status = ledger.get("companies", {}).get(ticker, {})
        refresh = {feed: {key: status[feed].get(key) or None for key in ("status", "attempted_at", "verified_at", "as_of")}
                   for feed in ("filings", "financials", "quarterly", "market", "news") if feed in status}
        if "filings" in refresh:
            for key in ("indexed_through", "distribution_source"):
                if isinstance(value := status["filings"].get(key), str) and value:
                    refresh["filings"][key] = value[:120]
        companies[ticker] = {
            "ticker": ticker, "name": COMPANY_NAMES[ticker], "sector": COMPANY_SECTORS[ticker], "role": COMPANY_ROLES[ticker],
            "annual": annual, "question": profile["key_questions"][0], "thesis": profile["research_thesis"],
            "counter_thesis": profile["counter_thesis"], "peers": list(EXPANDED_PEERS[ticker]), "cases": cases,
            "latest_filing": {key: filing[key] for key in ("form", "filed", "url")} if filing else None,
            "latest_quarter": quarterly_data,
            "latest_adjusted_close": closes.get(ticker),
            "news": [export_story(story) for story in stories], "refresh": refresh,
        }
    return {"schema_version": 1, "generated_at": generated_at.isoformat(), "companies": companies}


def write_lite_feed(path: Path, data: dict) -> None:
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    # Create the temporary file beside the final one so replacement remains atomic.
    with TemporaryDirectory(dir=path.parent) as folder:
        temporary = Path(folder) / path.name
        temporary.write_text(encoded, encoding="utf-8")
        temporary.replace(path)


if __name__ == "__main__":
    feed = build_lite_feed()
    write_lite_feed(DATA / "lite_briefs.json", feed)
    print(f"Exported {len(feed['companies'])} Lite company briefs.")
