from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news_connector import load_company_news, load_company_news_snapshot  # noqa: E402
from research_catalog import COMPANY_NAMES  # noqa: E402


def _refresh_company(item: tuple[str, str], *, limit: int, window_days: int) -> tuple[str, list[dict[str, str]]]:
    ticker, company = item
    stories = load_company_news(company, ticker, limit=limit, window_days=window_days)
    cutoff = date.today() - timedelta(days=window_days)
    for story in stories:
        published = date.fromisoformat(story["date"])
        if published < cutoff:
            raise RuntimeError(f"Outdated article for {ticker}: {story['date']} · {story['title']}")
        if story.get("image_kind") != "article" or not story.get("image", "").startswith("https://"):
            raise RuntimeError(f"Missing article cover for {ticker}: {story['title']}")
        if story["image"] == story["url"]:
            raise RuntimeError(f"Article page was mistaken for its cover for {ticker}: {story['title']}")
        if (urlparse(story["url"]).hostname or "").lower() == "news.google.com":
            raise RuntimeError(f"Unresolved publisher URL for {ticker}: {story['title']}")
    return ticker, stories


def _merge_stories(
    fresh: list[dict[str, str]],
    existing: list[dict[str, str]],
    *,
    limit: int,
) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen_titles: set[str] = set()
    seen_urls: set[str] = set()
    for story in [*fresh, *existing]:
        title_key = "".join(character.lower() for character in story["title"] if character.isalnum())[:140]
        url_key = story["url"].split("?", 1)[0].rstrip("/")
        if title_key in seen_titles or url_key in seen_urls:
            continue
        seen_titles.add(title_key)
        seen_urls.add(url_key)
        merged.append(story)
        if len(merged) >= limit:
            break
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh the verified rolling company-news snapshot.")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "recent_news.json")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--window-days", type=int, default=90)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")

    existing = {
        ticker: load_company_news_snapshot(
            ticker,
            limit=args.limit,
            window_days=args.window_days,
            path=args.output,
        )
        for ticker in COMPANY_NAMES
    }
    companies: dict[str, list[dict[str, str]]] = {}
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(_refresh_company, item, limit=args.limit, window_days=args.window_days): item[0]
            for item in COMPANY_NAMES.items()
        }
        for future in as_completed(futures):
            requested_ticker = futures[future]
            try:
                ticker, stories = future.result()
            except Exception as error:  # Preserve verified coverage when an external publisher is unavailable.
                failures.append(f"{requested_ticker}: {type(error).__name__}")
                companies[requested_ticker] = existing[requested_ticker]
                print(
                    f"{requested_ticker}: refresh unavailable; kept {len(existing[requested_ticker])} verified stories",
                    flush=True,
                )
                continue
            companies[ticker] = _merge_stories(stories, existing[ticker], limit=args.limit)
            print(f"{ticker}: {len(companies[ticker])} qualifying stories", flush=True)

    ordered = {ticker: companies.get(ticker, []) for ticker in COMPANY_NAMES}
    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "window_days": args.window_days,
        "companies": ordered,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    covered = sum(bool(stories) for stories in ordered.values())
    total = sum(len(stories) for stories in ordered.values())
    print(f"Refreshed {len(ordered)} companies: {covered} with coverage, {total} stories total.")
    if failures:
        print("Transient refresh failures: " + ", ".join(failures))


if __name__ == "__main__":
    main()
