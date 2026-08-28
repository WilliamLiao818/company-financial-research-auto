from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime


TRUSTED_DOMAINS = {
    "reuters.com": "Reuters",
    "wsj.com": "The Wall Street Journal",
    "nytimes.com": "The New York Times",
    "ft.com": "Financial Times",
    "bloomberg.com": "Bloomberg",
    "cnbc.com": "CNBC",
    "apnews.com": "Associated Press",
}

BUSINESS_TERMS = "earnings OR revenue OR AI OR cloud OR chips OR investment OR acquisition OR regulation OR product OR strategy"
MATERIAL_TITLE_TERMS = {
    "acquisition", "ai", "antitrust", "capacity", "ceo", "chip", "cloud",
    "deal", "demand", "earnings", "export", "forecast", "guidance",
    "investment", "launch", "lawsuit", "merger", "partnership", "product",
    "regulation", "revenue", "results", "strategy", "supply", "tariff",
}
LOW_VALUE_TITLE_PATTERNS = {
    "historical stock price", "market cap", "share price today", "stock price today",
    "stock quote", "technical analysis",
}
SEARCH_ALIASES = {
    "MSFT": ["Microsoft"], "ORCL": ["Oracle"], "GOOG": ["Google", "Alphabet"],
    "AVGO": ["Broadcom"], "SNDK": ["SanDisk", "Sandisk"], "NVDA": ["Nvidia"],
    "MRVL": ["Marvell"], "AAPL": ["Apple"], "AMZN": ["Amazon"], "META": ["Meta"],
    "LITE": ["Lumentum"], "AMAT": ["Applied Materials"], "TSM": ["TSMC", "Taiwan Semiconductor"],
    "ASML": ["ASML"], "AMD": ["AMD", "Advanced Micro Devices"],
}


def _domain(value: str) -> str:
    hostname = urllib.parse.urlparse(value).hostname or ""
    hostname = hostname.lower().removeprefix("www.")
    for domain in TRUSTED_DOMAINS:
        if hostname == domain or hostname.endswith("." + domain):
            return domain
    return ""


def _published_at(value: str) -> datetime | None:
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def load_company_news(
    company_name: str,
    ticker: str,
    *,
    limit: int = 4,
    window_days: int = 90,
    now: datetime | None = None,
) -> list[dict[str, str]]:
    short_name = company_name.replace(" Corporation", "").replace(" Inc.", "").replace(" plc", "")
    aliases = SEARCH_ALIASES.get(ticker, [short_name, ticker])
    company_filter = " OR ".join(f'"{alias}"' for alias in aliases)
    site_filter = " OR ".join(f"site:{domain}" for domain in TRUSTED_DOMAINS)
    query = f'({company_filter}) ({BUSINESS_TERMS}) when:{window_days}d ({site_filter})'
    params = urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    request = urllib.request.Request(
        "https://news.google.com/rss/search?" + params,
        headers={"User-Agent": "Mozilla/5.0 TheCompanyResearch/2.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            root = ET.fromstring(response.read())
    except (urllib.error.URLError, TimeoutError, ET.ParseError):
        return []

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    current_time = current_time.astimezone(timezone.utc)
    cutoff = current_time - timedelta(days=window_days)
    latest_allowed = current_time + timedelta(days=1)

    ranked_results: list[tuple[int, datetime, dict[str, str]]] = []
    seen: set[str] = set()
    for item in root.findall("./channel/item"):
        source = item.find("source")
        domain = _domain(source.get("url", "") if source is not None else "")
        if not domain:
            continue
        title = " ".join((item.findtext("title") or "").split())
        publisher = TRUSTED_DOMAINS[domain]
        for suffix in [f" - {publisher}", " - WSJ", " - Bloomberg.com", " - Reuters", " - CNBC", " - AP News"]:
            if title.endswith(suffix):
                title = title[: -len(suffix)].strip()
        lowered_title = title.lower()
        if not any(alias.lower() in lowered_title for alias in aliases):
            continue
        if any(pattern in lowered_title for pattern in LOW_VALUE_TITLE_PATTERNS):
            continue
        published_at = _published_at(item.findtext("pubDate") or "")
        if published_at is None or published_at < cutoff or published_at > latest_allowed:
            continue
        url = item.findtext("link") or ""
        key = "".join(character.lower() for character in title if character.isalnum())[:100]
        if not title or not url.startswith("https://") or key in seen:
            continue
        seen.add(key)
        materiality_score = sum(term in lowered_title for term in MATERIAL_TITLE_TERMS)
        ranked_results.append(
            (
                materiality_score,
                published_at,
                {
                    "title": title,
                    "url": url,
                    "publisher": publisher,
                    "date": published_at.date().isoformat(),
                    "image": f"https://www.google.com/s2/favicons?domain={domain}&sz=256",
                    "image_kind": "logo",
                },
            )
        )
    ranked_results.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [row[2] for row in ranked_results[:limit]]
