"""Read the public refresh ledger. Check times and observation dates have different meanings."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def freshness_lines(ticker: str) -> list[str]:
    ledger = read_json(DATA / "refresh_status.json").get("companies", {}).get(ticker, {})
    if not ledger:
        return ["Scheduled source checks are awaiting their first published result."]
    lines = []
    for key, label in [("filings", "SEC filings"), ("financials", "Annual statements"),
                       ("market", "Adjusted close"), ("news", "90-day news")]:
        item = ledger.get(key, {})
        if not item:
            lines.append(f"{label} · awaiting first check")
            continue
        status = item.get("status")
        checked = item.get("verified_at", "")
        observed = item.get("as_of", "")
        detail = []
        if observed:
            detail.append(f"data {observed}")
        if status == "retained":
            detail.append("last attempt unavailable · saved data retained")
        elif status == "lagging":
            detail.append("latest quote trails the benchmark session")
        elif status == "fallback":
            detail.append("financial-provider check · SEC figures on file retained when available")
        if checked:
            detail.append(f"checked {checked[:10]}")
            if (datetime.now(timezone.utc) - datetime.fromisoformat(checked)).total_seconds() > 72 * 3600:
                detail.append("check overdue")
        if key == "news" and status == "ok" and not observed:
            detail.append("no qualifying story")
        lines.append(f"{label} · " + " · ".join(detail))
    return lines


def latest_filing(ticker: str) -> dict:
    return read_json(DATA / "filings.json").get(ticker, {}).get("filing", {})


def reported_quarter(ticker: str, saved: dict) -> dict:
    candidate = read_json(DATA / "filings.json").get(ticker, {}).get("quarter", {})
    if candidate and (candidate["period_end"], candidate["filed"]) > (saved.get("period_end", ""), saved.get("filed", "")):
        return candidate
    return saved
