from __future__ import annotations

import json
import re
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
    "an ai oracle", "company announcement", "historical stock price", "magic quadrant", "market cap",
    "marketscape", "named a leader", "share price today", "stock price today",
    "stock quote", "stocks to watch", "technical analysis",
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
    hostname = (parsed.hostname or "").lower()
    lowered = candidate.lower()
    if parsed.scheme != "https" or not parsed.netloc:
        return ""
    if hostname.endswith(("googleusercontent.com", "gstatic.com")):
        return ""
    if any(marker in lowered for marker in ("favicon", "sprite", "avatar", "author", "logo", "icon", "placeholder")):
        return ""
    if parsed.path.rstrip("/").endswith("/pulse"):
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


def _usable_article_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not hostname:
        return False
    if hostname == "markets.ft.com" and parsed.path.startswith("/data/announce"):
        return False
    return True


def _decode_google_news_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if (parsed.hostname or "").lower() != "news.google.com":
        return url
    data_id = parsed.path.rstrip("/").split("/")[-1]
    if not data_id:
        return ""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=7) as response:
            page = response.read(1_500_000).decode("utf-8", errors="ignore")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return ""

    tag = ""
    for match in re.finditer(r"<div\b[^>]*\bdata-n-a-id=\"[^\"]+\"[^>]*>", page):
        candidate_tag = match.group(0)
        candidate_id = re.search(r"\bdata-n-a-id=\"([^\"]+)\"", candidate_tag)
        if candidate_id and candidate_id.group(1) == data_id:
            tag = candidate_tag
            break
    if not tag:
        tag = page
    timestamp_match = re.search(r"\bdata-n-a-ts=\"(\d+)\"", tag)
    signature_match = re.search(r"\bdata-n-a-sg=\"([^\"]+)\"", tag)
    if not timestamp_match or not signature_match:
        return ""

    request_body = [
        "Fbv4je",
        (
            '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,'
            'null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],'
            f'"{data_id}",{timestamp_match.group(1)},"{signature_match.group(1)}"]'
        ),
    ]
    payload = urllib.parse.urlencode({"f.req": json.dumps([[request_body]])}).encode("utf-8")
    rpc_request = urllib.request.Request(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute",
        data=payload,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(rpc_request, timeout=7) as response:
            body = response.read(1_500_000).decode("utf-8", errors="ignore")
        data = body.split("\n", 1)[-1]
        outer = json.loads(data)
        inner = json.loads(outer[0][2])
        original_url = str(inner[1])
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError, IndexError, json.JSONDecodeError):
        return ""
    original = urllib.parse.urlparse(original_url)
    if not _usable_article_url(original_url) or original.hostname == "news.google.com":
        return ""
    return original_url


def _article_metadata(url: str, expected_domain: str) -> tuple[str, str]:
    if not _host_matches(url, expected_domain):
        return url, ""
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
    article_url = canonical if _host_matches(canonical, expected_domain) else final_url if _host_matches(final_url, expected_domain) else ""
    if not article_url:
        return url, ""
    for value in parser.image_candidates:
        candidate = _valid_cover_url(value, base_url=article_url)
        if candidate:
            return article_url, candidate
    return article_url, ""


def _complete_story(row: tuple[int, datetime, dict[str, str], str]) -> tuple[int, datetime, dict[str, str]] | None:
    score, published_at, story, domain = row
    decoded_url = _decode_google_news_url(story["url"])
    if not decoded_url or not _host_matches(decoded_url, domain):
        return None
    if not _usable_article_url(decoded_url):
        return None
    article_url, image = _article_metadata(decoded_url, domain)
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


def _local_child_text(item: ET.Element, local_name: str) -> str:
    wanted = local_name.lower()
    for child in item:
        if str(child.tag).rsplit("}", 1)[-1].lower() == wanted:
            return child.text or ""
    return ""


def _bing_original_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if (parsed.hostname or "").lower() not in {"bing.com", "www.bing.com"}:
        return value if parsed.scheme == "https" else ""
    original = urllib.parse.parse_qs(parsed.query).get("url", [""])[0]
    decoded = urllib.parse.unquote(original)
    return decoded if decoded.startswith("https://") else ""


def _load_bing_company_news(
    aliases: list[str],
    publishers: dict[str, str],
    *,
    limit: int,
    window_days: int,
    current_time: datetime,
) -> list[dict[str, str]]:
    query = f'"{aliases[0]}" earnings AI cloud strategy investment product'
    params = urllib.parse.urlencode(
        {"q": query, "format": "rss", "setlang": "en-us", "cc": "us"}
    )
    request = urllib.request.Request(
        "https://www.bing.com/news/search?" + params,
        headers={"User-Agent": "Mozilla/5.0 TheCompanyResearch/2.2"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            root = ET.fromstring(response.read())
    except (urllib.error.URLError, TimeoutError, ET.ParseError, OSError):
        return []

    cutoff = current_time - timedelta(days=window_days)
    latest_allowed = current_time + timedelta(days=1)
    ranked: list[tuple[int, datetime, dict[str, str]]] = []
    seen: set[str] = set()
    for item in root.findall("./channel/item"):
        title = " ".join((item.findtext("title") or "").split())
        lowered_title = title.lower()
        if not any(alias.lower() in lowered_title for alias in aliases):
            continue
        if any(pattern in lowered_title for pattern in LOW_VALUE_TITLE_PATTERNS):
            continue
        published_at = _published_at(item.findtext("pubDate") or "")
        if published_at is None or published_at < cutoff or published_at > latest_allowed:
            continue
        original_url = _bing_original_url(item.findtext("link") or "")
        if not _usable_article_url(original_url):
            continue
        domain = _domain(original_url, publishers)
        if not domain:
            continue
        raw_image = _local_child_text(item, "Image")
        if raw_image.startswith("http://www.bing.com/"):
            raw_image = "https://www.bing.com/" + raw_image.removeprefix("http://www.bing.com/")
        image = _valid_cover_url(raw_image)
        if not image or "th?id=" not in image:
            original_url, image = _article_metadata(original_url, domain)
            if not image:
                continue
        key = "".join(character.lower() for character in title if character.isalnum())[:100]
        if not key or key in seen:
            continue
        seen.add(key)
        editorial_weight = 3 if domain in TRUSTED_DOMAINS and domain != "cnbc.com" else 2 if domain == "cnbc.com" else 1
        score = editorial_weight * 10 + sum(term in lowered_title for term in MATERIAL_TITLE_TERMS)
        ranked.append(
            (
                score,
                published_at,
                {
                    "title": title,
                    "url": original_url,
                    "publisher": publishers[domain],
                    "date": published_at.date().isoformat(),
                    "image": image,
                    "image_kind": "article",
                },
            )
        )
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [row[2] for row in ranked[:limit]]


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
    publishers = {**TRUSTED_DOMAINS, **OFFICIAL_DOMAINS_BY_TICKER.get(ticker, {})}
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    current_time = current_time.astimezone(timezone.utc)
    cutoff = current_time - timedelta(days=window_days)
    latest_allowed = current_time + timedelta(days=1)

    indexed_results = _load_bing_company_news(
        aliases,
        publishers,
        limit=limit,
        window_days=window_days,
        current_time=current_time,
    )
    if indexed_results:
        return indexed_results

    company_filter = " OR ".join(f'"{alias}"' for alias in aliases)
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
    except (urllib.error.URLError, TimeoutError, ET.ParseError, OSError):
        return []

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
        editorial_weight = 3 if domain in TRUSTED_DOMAINS and domain != "cnbc.com" else 2 if domain == "cnbc.com" else 1
        materiality_score = editorial_weight * 10 + sum(term in lowered_title for term in MATERIAL_TITLE_TERMS)
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
    candidates = ranked_results[: max(limit * 5, 20)]
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(candidates)))) as executor:
        completed = list(executor.map(_complete_story, candidates))
    available = [row for row in completed if row is not None]
    available.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [row[2] for row in available[:limit]]
