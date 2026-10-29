"""Public value-chain navigation, independent of company financial inputs.

Roles identify areas for research. Proximity in the map is not a statement that
two companies have a disclosed commercial relationship.
"""
from __future__ import annotations

from urllib.parse import urlencode

from research_catalog import COMPANY_NAMES


INDUSTRY_URL = "https://liaoresearch.com/industry"
COMPANY_URL = "https://company-financial-research-auto.streamlit.app/"

# Keep these stable IDs aligned with the public Industry map.
STAGE_TITLES = {
    "demand": "Cloud demand",
    "design": "Chip design",
    "eda": "Design tools & IP",
    "equipment": "Manufacturing equipment",
    "foundry": "Wafer fabrication",
    "memory": "Memory",
    "packaging": "Advanced packaging",
    "test": "Semiconductor test",
    "systems": "Servers & systems",
    "networking": "High-speed networking",
    "optics": "Optical connectivity",
    "power": "Power delivery",
    "cooling": "Thermal management",
    "deployment": "Cloud deployment",
}
STAGE_COMPANIES = {
    "demand": ("MSFT", "AMZN", "GOOG", "META", "ORCL"),
    "design": ("NVDA", "AMD", "AVGO", "MRVL"),
    "eda": ("SNPS", "CDNS", "ARM"),
    "equipment": ("ASML", "AMAT", "LRCX", "KLAC"),
    "foundry": ("TSM",),
    "memory": ("MU",),
    "packaging": ("TSM", "AMKR"),
    "test": ("TER",),
    "systems": ("DELL", "SMCI", "HPE"),
    "networking": ("ANET", "NVDA", "AVGO"),
    "optics": ("LITE", "COHR", "FN"),
    "power": ("ETN", "VRT", "MPWR"),
    "cooling": ("VRT",),
    "deployment": ("MSFT", "AMZN", "ORCL", "GOOG", "META"),
}
THEME_TITLES = {
    "ai-compute": "AI compute",
    "power-cooling": "Power & cooling",
    "networking": "Networking & optics",
}
THEME_STAGES = {
    "ai-compute": ("demand", "eda", "design", "equipment", "foundry", "memory", "packaging", "test", "systems", "deployment"),
    "power-cooling": ("demand", "design", "power", "cooling", "systems", "deployment"),
    "networking": ("demand", "design", "optics", "networking", "systems", "deployment"),
}
# Related research is organized by nearby roles, not assumed supply contracts.
NEARBY_STAGES = {
    "demand": ("design", "systems", "deployment"),
    "design": ("eda", "foundry", "memory", "networking"),
    "eda": ("design", "foundry"),
    "equipment": ("foundry", "memory", "packaging"),
    "foundry": ("equipment", "design", "packaging"),
    "memory": ("design", "packaging", "systems"),
    "packaging": ("foundry", "memory", "test"),
    "test": ("packaging", "systems"),
    "systems": ("design", "networking", "power", "cooling"),
    "networking": ("optics", "systems", "design"),
    "optics": ("networking", "systems"),
    "power": ("cooling", "systems", "deployment"),
    "cooling": ("power", "systems", "deployment"),
    "deployment": ("systems", "power", "networking"),
}


def _normalized_ticker(ticker: str) -> str | None:
    cleaned = str(ticker).strip().upper()
    return cleaned if cleaned in COMPANY_NAMES else None


def company_url(ticker: str) -> str | None:
    """Only generate links for known public research packs."""
    normalized = _normalized_ticker(ticker)
    return f"{COMPANY_URL}?{urlencode({'ticker': normalized})}" if normalized else None


def map_url(ticker: str, theme: str = "ai-compute") -> str | None:
    normalized = _normalized_ticker(ticker)
    if normalized is None or theme not in THEME_STAGES:
        return None
    if not any(normalized in STAGE_COMPANIES[stage] for stage in THEME_STAGES[theme]):
        return None
    return f"{INDUSTRY_URL}?{urlencode({'company': normalized, 'theme': theme})}"


def context_for(ticker: str) -> dict[str, object] | None:
    """Return a compact public map context or None for unmapped companies."""
    normalized = _normalized_ticker(ticker)
    if normalized is None:
        return None
    roles = tuple(stage for stage, tickers in STAGE_COMPANIES.items() if normalized in tickers)
    if not roles:
        return None
    primary_theme = (
        "power-cooling" if {"power", "cooling"}.intersection(roles)
        else "networking" if "optics" in roles or ("networking" in roles and "design" not in roles)
        else "ai-compute"
    )
    themes = [primary_theme, *(theme for theme in THEME_TITLES if theme != primary_theme)]
    theme_links = [
        {"id": theme, "title": THEME_TITLES[theme], "url": url}
        for theme in themes if (url := map_url(normalized, theme))
    ]
    # Round-robin adjacent roles so a narrow peer list cannot hide the chain.
    neighbor_roles = list(dict.fromkeys(stage for role in roles for stage in NEARBY_STAGES[role]))
    related: list[dict[str, str]] = []
    seen = {normalized}
    for offset in range(max(len(STAGE_COMPANIES[stage]) for stage in neighbor_roles)):
        for stage in neighbor_roles:
            options = STAGE_COMPANIES[stage]
            if offset >= len(options):
                continue
            candidate = options[offset]
            if candidate in seen:
                continue
            seen.add(candidate)
            related.append({
                "ticker": candidate,
                "name": COMPANY_NAMES[candidate],
                "role": STAGE_TITLES[stage],
                "url": company_url(candidate) or "",
            })
            if len(related) == 4:
                break
        if len(related) == 4:
            break
    return {
        "ticker": normalized,
        "stage_ids": roles,
        "roles": tuple(STAGE_TITLES[stage] for stage in roles),
        "map_url": map_url(normalized, primary_theme),
        "theme_links": theme_links,
        "related": related,
    }
