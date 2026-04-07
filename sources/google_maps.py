"""Lightweight Google Maps discovery using Scrapling StealthyFetcher.

This is a best-effort implementation. For production volume, prefer the
gosom/google-maps-scraper Docker image (see README).
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus

from loguru import logger

from config.settings import MAX_DESCRIPTION_CHARS
from core.browser import fetch
from core.deduplication import normalize_domain
from core.models import Prospect, Source, Vertical

WEBSITE_RE = re.compile(r"https?://(?!(?:www\.)?google\.[a-z.]+)[\w\-.]+\.[a-z]{2,}[\w\-/?#%&=.]*")
RATING_RE = re.compile(r'"rating":\s*([\d.]+)')
REVIEWS_RE = re.compile(r'"reviews_count":\s*(\d+)')


def _search_url(query: str) -> str:
    return f"https://www.google.com/maps/search/{quote_plus(query)}"


def discover(query: str, vertical: Vertical, max_results: int = 20) -> list[Prospect]:
    """Scrape Google Maps search results. Returns basic Prospect stubs."""
    url = _search_url(query)
    page = fetch(url, stealth=True)
    if page is None:
        logger.warning(f"Maps fetch returned nothing for '{query}'")
        return []

    html = getattr(page, "html_content", "") or getattr(page, "body", "") or ""
    if not html:
        return []

    # Extract external website URLs found in the Maps SPA JSON blob
    prospects: list[Prospect] = []
    seen: set[str] = set()
    for m in WEBSITE_RE.finditer(html):
        link = m.group(0)
        # Trim trailing junk
        link = link.split('"')[0].split("\\")[0]
        domain = normalize_domain(link)
        if not domain or domain in seen:
            continue
        if any(b in domain for b in (
            "gstatic", "googleapis", "googleusercontent", "google.com",
            "schema.org", "w3.org", "youtube", "facebook", "instagram",
        )):
            continue
        seen.add(domain)
        prospects.append(Prospect(
            company_name=domain.split(".")[0].title(),
            website=f"https://{domain}",
            domain=domain,
            vertical=vertical,
            source=Source.GOOGLE_MAPS,
            source_query=query,
            description=f"Discovered via Google Maps search: {query}"[:MAX_DESCRIPTION_CHARS],
        ))
        if len(prospects) >= max_results:
            break

    logger.info(f"Google Maps '{query}' -> {len(prospects)} prospects")
    return prospects
