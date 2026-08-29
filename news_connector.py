from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser


TRUSTED_DOMAINS = {
    "reuters.com": "Reuters",
    "wsj.com": "The Wall Street Journal",
    "nytimes.com": "The New York Times",
    "ft.com": "Financial Times",
    "bloomberg.com": "Bloomberg",
    "cnbc.com": "CNBC",
    "apnews.com": "Associated Press",
}

OFFICIAL_DOMAINS_BY_TICKER = {
    "MSFT": {"microsoft.com": "Microsoft"},
    "ORCL": {"oracle.com": "Oracle"},
    "GOOG": {"blog.google": "Google"},
    "AVGO": {"broadcom.com": "Broadcom"},
    "SNDK": {"sandisk.com": "SanDisk"},
    "NVDA": {"nvidia.com": "NVIDIA"},
    "MRVL": {"marvell.com": "Marvell"},
    "AAPL": {"apple.com": "Apple"},
    "AMZN": {"aboutamazon.com": "Amazon"},
    "META": {"about.fb.com": "Meta"},
    "LITE": {"lumentum.com": "Lumentum"},
    "AMAT": {"appliedmaterials.com": "Applied Materials"},
    "TSM": {"tsmc.com": "TSMC"},
    "ASML": {"asml.com": "ASML"},
    "AMD": {"amd.com": "AMD"},
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
MEDIA_CONTENT = "{http://search.yahoo.com/mrss/}content"
MEDIA_THUMBNAIL = "{http://search.yahoo.com/mrss/}thumbnail"


class _ArticleMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.image_candidates: list[str] = []
        self.canonical_url = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {str(key).lower(): str(value or "").strip() for key, value in attrs}
        if tag.lower() == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            if key in {"og:image", "og:image:secure_url", "twitter:image", "twitter:image:src"}:
                self.image_candidates.append(values.get("content", ""))
        elif tag.lower() == "link" and "canonical" in values.get("rel", "").lower():
            self.canonical_url = values.get("href", "")
        elif tag.lower() == "img":
            self.image_candidates.append(values.get("src", ""))


def _valid_cover_url(value: str, *, base_url: str = "") -> str:
    candidate = urllib.parse.urljoin(base_url, value.strip())
    parsed = urllib.parse.urlparse(candidate)
    lowered = candidate.lower()
    if parsed.scheme != "https" or not parsed.netloc:
        return ""
    if any(marker in lowered for marker in ("favicon", "sprite", "avatar", "author", "logo", "icon")):
        return ""
    if lowered.endswith((".svg", ".gif")):
        return ""
    return candidate


def _rss_cover(item: ET.Element) -> str:
    for tag in (MEDIA_CONTENT, MEDIA_THUMBNAIL):
        for media in item.findall(tag):
            candidate = _valid_cover_url(media.get("url", ""))
            if candidate:
                return candidate
    enclosure = item.find("enclosure")
    if enclosure is not None and str(enclosure.get("type", "")).startswith("image/"):
        candidate = _valid_cover_url(enclosure.get("url", ""))
        if candidate:
            return candidate
    description = item.findtext("description") or ""
    parser = _ArticleMetadataParser()
    try:
        parser.feed(description)
    except (ValueError, TypeError):
        return ""
    for value in parser.image_candidates:
        candidate = _valid_cover_url(value)
        if candidate:
            return candidate
    return ""


def _host_matches(value: str, expected_domain: str) -> bool:
    hostname = (urllib.parse.urlparse(value).hostname or "").lower().removeprefix("www.")
    return hostname == expected_domain or hostname.endswith("." + expected_domain)


def _article_metadata(url: str, expected_domain: str) -> tuple[str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=7) as response:
            final_url = response.geturl() if hasattr(response, "geturl") else url
            payload = response.read(2_500_000)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return url, ""
    try:
        text = payload.decode("utf-8", errors="ignore")
        parser = _ArticleMetadataParser()
        parser.feed(text)
    except (UnicodeError, ValueError, TypeError):
        return url, ""

    canonical = urllib.parse.urljoin(final_url, parser.canonical_url) if parser.canonical_url else final_url
    article_url = canonical if _host_matches(canonical, expected_domain) else final_url if _host_matches(final_url, expected_domain) else url
    for value in parser.image_candidates:
        candidate = _valid_cover_url(value, base_url=article_url)
        if candidate:
            return article_url, candidate
    return article_url, ""


def _complete_story(row: tuple[int, datetime, dict[str, str], str]) -> tuple[int, datetime, dict[str, str]] | None:
    score, published_at, story, domain = row
    if story.get("image"):
        return score, published_at, story
    article_url, image = _article_metadata(story["url"], domain)
    if not image:
        return None
    completed = {**story, "url": article_url, "image": image, "image_kind": "article"}
    return score, published_at, completed


def _domain(value: str, domains: dict[str, str] | None = None) -> str:
    hostname = urllib.parse.urlparse(value).hostname or ""
    hostname = hostname.lower().removeprefix("www.")
    for domain in domains or TRUSTED_DOMAINS:
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
    publishers = {**TRUSTED_DOMAINS, **OFFICIAL_DOMAINS_BY_TICKER.get(ticker, {})}
    site_filter = " OR ".join(f"site:{domain}" for domain in publishers)
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

    ranked_results: list[tuple[int, datetime, dict[str, str], str]] = []
    seen: set[str] = set()
    for item in root.findall("./channel/item"):
        source = item.find("source")
        domain = _domain(source.get("url", "") if source is not None else "", publishers)
        if not domain:
            continue
        title = " ".join((item.findtext("title") or "").split())
        publisher = publishers[domain]
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
        cover = _rss_cover(item)
        ranked_results.append(
            (
                materiality_score,
                published_at,
                {
                    "title": title,
                    "url": url,
                    "publisher": publisher,
                    "date": published_at.date().isoformat(),
                    "image": cover,
                    "image_kind": "article" if cover else "",
                },
                domain,
            )
        )
    ranked_results.sort(key=lambda row: (row[0], row[1]), reverse=True)
    candidates = ranked_results[: max(limit * 3, limit)]
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(candidates)))) as executor:
        completed = list(executor.map(_complete_story, candidates))
    available = [row for row in completed if row is not None]
    available.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [row[2] for row in available[:limit]]
