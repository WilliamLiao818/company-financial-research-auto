"""Read the public refresh ledger. Check times and observation dates have different meanings."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from provider_quarter import choose_quarter

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
                       ("quarterly", "Quarterly statements"), ("market", "Adjusted close"), ("news", "90-day news")]:
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
        elif key == "filings" and status in {"distribution", "delayed"}:
            detail.append(f"SEC EDGAR via Listed · index through {item.get('indexed_through', 'unknown')}")
            if status == "delayed":
                detail.append("filing index delayed")
        elif key == "quarterly" and status == "delayed":
            detail.append("provider trails the quarterly statement on file")
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
    return choose_quarter(saved, candidate)
