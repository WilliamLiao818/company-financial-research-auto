from __future__ import annotations

import json
import http.client
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path


TRUSTED_DOMAINS = {
    "reuters.com": "Reuters",
    "wsj.com": "The Wall Street Journal",
    "nytimes.com": "The New York Times",
    "ft.com": "Financial Times",
    "bloomberg.com": "Bloomberg",
    "cnbc.com": "CNBC",
    "apnews.com": "Associated Press",
    "fortune.com": "Fortune",
    "axios.com": "Axios",
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
    "INTC": {"intel.com": "Intel"},
    "QCOM": {"qualcomm.com": "Qualcomm"},
    "MU": {"micron.com": "Micron"},
    "TXN": {"ti.com": "Texas Instruments"},
    "ADI": {"analog.com": "Analog Devices", "alifsemi.com": "Alif Semiconductor"},
    "NXPI": {"nxp.com": "NXP Semiconductors"},
    "ARM": {"arm.com": "Arm"},
    "MCHP": {"microchip.com": "Microchip Technology"},
    "ON": {"onsemi.com": "onsemi"},
    "GFS": {"gf.com": "GlobalFoundries"},
    "KLAC": {"kla.com": "KLA"},
    "LRCX": {"lamresearch.com": "Lam Research"},
    "TER": {"teradyne.com": "Teradyne"},
    "CDNS": {"cadence.com": "Cadence"},
    "SNPS": {"synopsys.com": "Synopsys"},
    "AMKR": {"amkor.com": "Amkor Technology"},
    "ENTG": {"entegris.com": "Entegris"},
    "COHR": {"coherent.com": "Coherent"},
    "ANET": {"arista.com": "Arista Networks"},
    "CSCO": {"cisco.com": "Cisco"},
    "DELL": {"dell.com": "Dell Technologies"},
    "HPE": {"hpe.com": "Hewlett Packard Enterprise", "channelnewsasia.com": "Reuters / CNA"},
    "VRT": {"vertiv.com": "Vertiv"},
    "SMCI": {"supermicro.com": "Supermicro", "prnewswire.com": "Super Micro Computer, Inc. / PR Newswire"},
    "WDC": {"westerndigital.com": "Western Digital"},
    "CRM": {"salesforce.com": "Salesforce"},
    "NOW": {"servicenow.com": "ServiceNow"},
    "PANW": {"paloaltonetworks.com": "Palo Alto Networks"},
    "PLTR": {"palantir.com": "Palantir", "nebius.com": "Nebius"},
    "TSLA": {"tesla.com": "Tesla"},
    "V": {"visa.com": "Visa"},
    "LLY": {"lilly.com": "Eli Lilly"},
    "WMT": {"walmart.com": "Walmart"},
    "GEV": {"gevernova.com": "GE Vernova"},
    "CAT": {"caterpillar.com": "Caterpillar"},
}

BUSINESS_TERMS = "earnings OR revenue OR AI OR cloud OR chips OR investment OR acquisition OR regulation OR product OR strategy"
MATERIAL_TITLE_TERMS = {
    "acquire", "acquired", "acquires", "acquisition", "acquisitions", "ai", "annual", "antitrust", "approval",
    "approved", "capacity", "ceo", "chip", "chips", "cloud", "contract", "contracts", "data center",
    "data centers", "deal", "deals", "demand", "earnings", "export", "exports", "factories", "factory",
    "forecast", "forecasts", "guidance", "invested", "investing", "investigation", "investigations", "investment",
    "investments", "job", "jobs", "launch", "launched", "launches", "lawsuit", "lawsuits", "merger", "mergers",
    "partnership", "partnerships", "product", "products", "profit", "profits", "quarter", "quarterly", "quarters",
    "recall", "recalls", "regulation", "regulations", "result", "results", "revenue", "revenues", "sale", "sales",
    "security", "spend", "spending", "strategy", "strategies", "supply", "supplies", "tariff", "tariffs",
    "buy", "buys", "purchase", "purchases",
}
LOW_VALUE_TITLE_PATTERNS = {
    "an ai oracle", "company announcement", "historical stock price", "magic quadrant", "market cap",
    "marketscape", "named a leader", "share price today", "stock price today",
    "stock quote", "stocks to watch", "technical analysis", "how to use options",
    "options to generate income", "should you buy", "is it too late to buy",
    "price target", "stock pick", "stocks to buy", "top stock", "wall street ends",
    "wall st week ahead", "the best early deals", "prime big deal days",
    "could ai chip boom make", "ceo as adviser", "trillion club",
}
SEARCH_ALIASES = {
    "MSFT": ["Microsoft"], "ORCL": ["Oracle"], "GOOG": ["Google", "Alphabet"],
    "AVGO": ["Broadcom"], "SNDK": ["SanDisk", "Sandisk"], "NVDA": ["Nvidia"],
    "MRVL": ["Marvell"], "AAPL": ["Apple"], "AMZN": ["Amazon"], "META": ["Meta"],
    "LITE": ["Lumentum"], "AMAT": ["Applied Materials"], "TSM": ["TSMC", "Taiwan Semiconductor"],
    "ASML": ["ASML"], "AMD": ["AMD", "Advanced Micro Devices"],
    "INTC": ["Intel"], "QCOM": ["Qualcomm"], "MU": ["Micron", "Micron Technology"],
    "TXN": ["Texas Instruments"], "ADI": ["Analog Devices"],
    "NXPI": ["NXP Semiconductors", "NXP"], "ARM": ["Arm Holdings", "Arm Holdings plc"],
    "MCHP": ["Microchip Technology"], "ON": ["onsemi"],
    "GFS": ["GlobalFoundries"], "KLAC": ["KLA Corporation", "KLA"],
    "LRCX": ["Lam Research"], "TER": ["Teradyne"],
    "CDNS": ["Cadence Design Systems", "Cadence"], "SNPS": ["Synopsys"],
    "AMKR": ["Amkor Technology", "Amkor"], "ENTG": ["Entegris"],
    "COHR": ["Coherent Corp", "Coherent"], "ANET": ["Arista Networks"],
    "CSCO": ["Cisco Systems", "Cisco"], "DELL": ["Dell Technologies", "Dell"],
    "HPE": ["Hewlett Packard Enterprise", "HPE"], "VRT": ["Vertiv Holdings", "Vertiv"],
    "SMCI": ["Super Micro Computer", "Supermicro"], "WDC": ["Western Digital"],
    "CRM": ["Salesforce"], "NOW": ["ServiceNow"],
    "PANW": ["Palo Alto Networks"], "PLTR": ["Palantir Technologies", "Palantir"],
    "TSLA": ["Tesla"], "V": ["Visa Inc", "Visa"],
    "LLY": ["Eli Lilly", "Lilly"], "WMT": ["Walmart"],
    "GEV": ["GE Vernova"], "CAT": ["Caterpillar"],
}
MEDIA_CONTENT = "{http://search.yahoo.com/mrss/}content"
MEDIA_THUMBNAIL = "{http://search.yahoo.com/mrss/}thumbnail"
NEWS_SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "recent_news.json"


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
    raw_value = value.strip()
    if not raw_value:
        return ""
    candidate = urllib.parse.urljoin(base_url, raw_value)
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
    normalized_host = hostname.removeprefix("www.")
    if parsed.scheme != "https" or not hostname:
        return False
    if hostname == "markets.ft.com" and parsed.path.startswith("/data/announce"):
        return False
    if normalized_host == "reuters.com" and parsed.path.startswith("/plus/"):
        return False
    if normalized_host.endswith("live.ft.com") or "/agenda/" in parsed.path:
        return False
    return True


def _title_matches_alias(title: str, aliases: list[str]) -> bool:
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])", title.lower())
        for alias in aliases
    )


def _materiality_count(title: str) -> int:
    lowered = title.lower()
    return sum(
        bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", lowered))
        for term in MATERIAL_TITLE_TERMS
    )


def _dated_article_time(url: str, fallback: datetime) -> datetime:
    """Prefer the publication date embedded in Reuters' canonical article URL."""
    hostname = (urllib.parse.urlparse(url).hostname or "").lower().removeprefix("www.")
    if hostname != "reuters.com":
        return fallback
    matched = re.search(r"-(\d{4}-\d{2}-\d{2})/?$", urllib.parse.urlparse(url).path)
    if not matched:
        return fallback
    try:
        return datetime.fromisoformat(matched.group(1)).replace(tzinfo=timezone.utc)
    except ValueError:
        return fallback


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
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, http.client.HTTPException):
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
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        TypeError,
        IndexError,
        json.JSONDecodeError,
        http.client.HTTPException,
    ):
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
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, http.client.HTTPException):
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
    image = image or _valid_cover_url(story.get("image", ""), base_url=article_url)
    image = image or _bing_cover_for_title(story["title"])
    if not image:
        return None
    article_time = _dated_article_time(article_url, published_at)
    completed = {
        **story,
        "url": article_url,
        "date": article_time.date().isoformat(),
        "image": image,
        "image_kind": "article",
    }
    return score, article_time, completed


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


def _bing_thumbnail(value: str) -> str:
    if value.startswith("http://www.bing.com/"):
        value = "https://www.bing.com/" + value.removeprefix("http://www.bing.com/")
    parsed = urllib.parse.urlparse(value)
    if (parsed.hostname or "").lower() not in {"bing.com", "www.bing.com"} or parsed.path != "/th":
        return ""
    parameters = urllib.parse.parse_qs(parsed.query)
    if not parameters.get("id"):
        return ""
    parameters.update({"w": ["1200"], "h": ["675"], "c": ["14"], "rs": ["2"], "qlt": ["90"]})
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(parameters, doseq=True)))


def _title_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())[:140]


def _bing_cover_for_title(title: str) -> str:
    """Resolve an article-specific cached thumbnail without replacing the original article URL."""
    wanted = _title_key(title)
    broad_terms = " ".join(re.findall(r"[A-Za-z0-9]+", title)[:14])
    for query in (f'"{title}"', broad_terms):
        params = urllib.parse.urlencode(
            {"q": query, "format": "rss", "setlang": "en-us", "cc": "us"}
        )
        request = urllib.request.Request(
            "https://www.bing.com/news/search?" + params,
            headers={"User-Agent": "Mozilla/5.0 TheCompanyResearch/2.2"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                root = ET.fromstring(response.read())
        except (
            urllib.error.URLError,
            TimeoutError,
            ET.ParseError,
            OSError,
            ValueError,
            http.client.HTTPException,
        ):
            continue
        for item in root.findall("./channel/item")[:8]:
            candidate_title = " ".join((item.findtext("title") or "").split())
            candidate = _title_key(candidate_title)
            if not wanted or (candidate != wanted and wanted not in candidate and candidate not in wanted):
                continue
            image = _valid_cover_url(_bing_thumbnail(_local_child_text(item, "Image")))
            if image:
                return image
    html_params = urllib.parse.urlencode({"q": broad_terms, "setlang": "en-us", "cc": "us"})
    html_request = urllib.request.Request(
        "https://www.bing.com/news/search?" + html_params,
        headers={"User-Agent": "Mozilla/5.0 TheCompanyResearch/2.2"},
    )
    try:
        with urllib.request.urlopen(html_request, timeout=10) as response:
            page = response.read(1_500_000).decode("utf-8", errors="ignore")
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        UnicodeError,
        http.client.HTTPException,
    ):
        return ""
    match = re.search(r'(?:data-src-hq|src)="([^\"]*/th\?id=ONUT\.[^\"]+)"', page)
    if match:
        cached = urllib.parse.urljoin("https://www.bing.com", match.group(1).replace("&amp;", "&"))
        return _valid_cover_url(_bing_thumbnail(cached))
    return ""


def _load_bing_company_news(
    aliases: list[str],
    publishers: dict[str, str],
    *,
    limit: int,
    window_days: int,
    current_time: datetime,
) -> list[dict[str, str]]:
    query = f'"{aliases[0]}" ({BUSINESS_TERMS})'
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
    except (urllib.error.URLError, TimeoutError, ET.ParseError, OSError, http.client.HTTPException):
        return []

    cutoff = current_time - timedelta(days=window_days)
    latest_allowed = current_time + timedelta(days=1)
    ranked: list[tuple[int, datetime, dict[str, str]]] = []
    seen: set[str] = set()
    for item in root.findall("./channel/item"):
        title = " ".join((item.findtext("title") or "").split())
        lowered_title = title.lower()
        if any(pattern in lowered_title for pattern in LOW_VALUE_TITLE_PATTERNS):
            continue
        published_at = _published_at(item.findtext("pubDate") or "")
        if published_at is None:
            continue
        original_url = _bing_original_url(item.findtext("link") or "")
        if not _usable_article_url(original_url):
            continue
        published_at = _dated_article_time(original_url, published_at)
        if published_at < cutoff or published_at > latest_allowed:
            continue
        domain = _domain(original_url, publishers)
        if not domain:
            continue
        is_official = domain not in TRUSTED_DOMAINS
        if not is_official and not _title_matches_alias(title, aliases):
            continue
        materiality_count = _materiality_count(title)
        if not is_official and not materiality_count:
            continue
        raw_image = _bing_thumbnail(_local_child_text(item, "Image"))
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
        score = editorial_weight * 10 + materiality_count
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
    if len(indexed_results) >= limit:
        return indexed_results[:limit]

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
    except (urllib.error.URLError, TimeoutError, ET.ParseError, OSError, http.client.HTTPException):
        return indexed_results

    ranked_results: list[tuple[int, datetime, dict[str, str], str]] = []
    seen: set[str] = {
        "".join(character.lower() for character in story["title"] if character.isalnum())[:100]
        for story in indexed_results
    }
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
        is_official = domain not in TRUSTED_DOMAINS
        if not is_official and not _title_matches_alias(title, aliases):
            continue
        if any(pattern in lowered_title for pattern in LOW_VALUE_TITLE_PATTERNS):
            continue
        materiality_count = _materiality_count(title)
        if not is_official and not materiality_count:
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
        materiality_score = editorial_weight * 10 + materiality_count
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
    combined = [*indexed_results, *(row[2] for row in available)]

    def priority(story: dict[str, str]) -> tuple[int, str]:
        domain = _domain(story["url"], publishers)
        editorial_weight = 3 if domain in TRUSTED_DOMAINS and domain != "cnbc.com" else 2 if domain == "cnbc.com" else 1
        lowered_title = story["title"].lower()
        score = editorial_weight * 10 + _materiality_count(story["title"])
        return score, story["date"]

    combined.sort(key=priority, reverse=True)
    deduplicated: list[dict[str, str]] = []
    seen_titles: set[str] = set()
    seen_urls: set[str] = set()
    publisher_counts: dict[str, int] = {}
    for story in combined:
        title_key = "".join(character.lower() for character in story["title"] if character.isalnum())[:100]
        parsed_url = urllib.parse.urlparse(story["url"])
        url_key = urllib.parse.urlunparse(parsed_url._replace(query="", fragment="")).rstrip("/")
        if title_key in seen_titles or url_key in seen_urls:
            continue
        publisher = story["publisher"]
        if publisher_counts.get(publisher, 0) >= 2:
            continue
        seen_titles.add(title_key)
        seen_urls.add(url_key)
        publisher_counts[publisher] = publisher_counts.get(publisher, 0) + 1
        deduplicated.append(story)
    return deduplicated[:limit]


def load_company_news_snapshot(
    ticker: str,
    *,
    limit: int = 4,
    window_days: int = 90,
    now: datetime | None = None,
    path: Path | str = NEWS_SNAPSHOT_PATH,
) -> list[dict[str, str]]:
    """Read the latest verified refresh as a fallback when live indexes are unavailable."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return []
    stories = payload.get("companies", {}).get(ticker, [])
    if not isinstance(stories, list):
        return []
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    current_date = current_time.astimezone(timezone.utc).date()
    cutoff = current_date - timedelta(days=window_days)
    latest_allowed = current_date + timedelta(days=1)
    aliases = SEARCH_ALIASES.get(ticker, [ticker])
    publishers = {**TRUSTED_DOMAINS, **OFFICIAL_DOMAINS_BY_TICKER.get(ticker, {})}
    verified: list[dict[str, str]] = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        try:
            published = datetime.fromisoformat(str(story.get("date", ""))).date()
        except ValueError:
            continue
        if published < cutoff or published > latest_allowed:
            continue
        article_url = str(story.get("url", ""))
        image_url = str(story.get("image", ""))
        title = str(story.get("title", ""))
        lowered_title = title.lower()
        if story.get("image_kind") != "article" or not _usable_article_url(article_url):
            continue
        domain = _domain(article_url, publishers)
        if not domain or any(pattern in lowered_title for pattern in LOW_VALUE_TITLE_PATTERNS):
            continue
        if domain in TRUSTED_DOMAINS and (not _title_matches_alias(title, aliases) or not _materiality_count(title)):
            continue
        if image_url == article_url or not _valid_cover_url(image_url):
            continue
        verified.append({key: str(story.get(key, "")) for key in ("title", "url", "publisher", "date", "image", "image_kind")})
    verified.sort(key=lambda story: story["date"], reverse=True)
    return verified[:limit]
