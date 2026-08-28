from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news_connector import load_company_news  # noqa: E402
from research_catalog import COMPANY_NAMES  # noqa: E402


def main() -> None:
    cutoff = date.today() - timedelta(days=90)
    for ticker, company in COMPANY_NAMES.items():
        stories = load_company_news(company, ticker)
        for story in stories:
            published = date.fromisoformat(story["date"])
            if published < cutoff:
                raise RuntimeError(f"Outdated article for {ticker}: {story['date']} · {story['title']}")
        dates = ", ".join(story["date"] for story in stories) or "no qualifying coverage"
        print(f"{ticker}: {dates}")


if __name__ == "__main__":
    main()
