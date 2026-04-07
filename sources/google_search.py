"""Google Search source. Prefers Serper.dev API; falls back to raw scraping."""
from __future__ import annotations

import random
import time
from typing import Optional
from urllib.parse import quote_plus, urlparse

import httpx
from loguru import logger

from config.blacklists import DOMAIN_BLACKLIST
from config.settings import DEFAULT_TIMEOUT, SERPER_API_KEY, has_serper
from core.browser import fetch
from core.deduplication import normalize_domain
from core.models import Prospect, Source, Vertical


def _build_prospect(
    title: str,
    link: str,
    snippet: str,
    vertical: Vertical,
    query: str,
) -> Optional[Prospect]:
    if not link or not title:
        return None
    domain = normalize_domain(link)
    if not domain or domain in DOMAIN_BLACKLIST:
        return None
    # Skip obvious non-company results
    if any(part in domain for part in ("google.", "youtube.", "wikipedia.", "facebook.")):
        return None

    # Best-effort company name from title (strip "- Site" / "| Site" trailing bits)
    name = title
    for sep in (" | ", " - ", " — ", " · "):
        if sep in name:
            name = name.split(sep)[0].strip()
    name = name.strip() or domain

    return Prospect(
        company_name=name,
        domain=domain,
        website=f"https://{domain}",
        vertical=vertical,
        source=Source.GOOGLE_SEARCH,
        source_query=query,
        description=(snippet or "")[:300],
    )


def search_serper(query: str, num_results: int = 20) -> list[dict]:
    """Call Serper.dev. Returns list of {title, link, snippet}."""
    if not SERPER_API_KEY:
        return []
    try:
        resp = httpx.post(
            "https://google.serper.dev/search",
            json={"q": query, "num": num_results},
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("organic", []) or []
    except Exception as e:
        logger.warning(f"Serper.dev error for '{query}': {e}")
        return []


def search_google_raw(query: str, pages: int = 2) -> list[dict]:
    """Raw Google scrape fallback using StealthyFetcher."""
    results: list[dict] = []
    for page in range(pages):
        start = page * 10
        url = f"https://www.google.com/search?q={quote_plus(query)}&start={start}&hl=en"
        page_obj = fetch(url, stealth=True)
        if page_obj is None:
            logger.warning(f"Google raw fetch returned nothing for '{query}'")
            break
        try:
            blocks = page_obj.css("div.g") or []
        except Exception:
            blocks = []
        for item in blocks:
            try:
                a = item.css_first("a")
                h3 = item.css_first("h3")
                snip = item.css_first("div.VwiC3b") or item.css_first("span.aCOpRe")
                if a is None or h3 is None:
                    continue
                link = a.attrib.get("href", "") if hasattr(a, "attrib") else ""
                title = h3.text if hasattr(h3, "text") else ""
                snippet = snip.text if snip and hasattr(snip, "text") else ""
                if link and title:
                    results.append({"title": title, "link": link, "snippet": snippet})
            except Exception:
                continue
        time.sleep(random.uniform(3, 8))
    return results


def discover(query: str, vertical: Vertical, num_results: int = 20) -> list[Prospect]:
    """Run a single query and return deduped prospects."""
    if has_serper():
        raw = search_serper(query, num_results=num_results)
    else:
        pages = max(1, (num_results + 9) // 10)
        raw = search_google_raw(query, pages=pages)

    prospects: list[Prospect] = []
    seen: set[str] = set()
    for r in raw:
        p = _build_prospect(
            title=r.get("title", ""),
            link=r.get("link", ""),
            snippet=r.get("snippet", ""),
            vertical=vertical,
            query=query,
        )
        if not p or p.domain in seen:
            continue
        seen.add(p.domain)
        prospects.append(p)
    logger.info(f"Google search '{query}' -> {len(prospects)} prospects")
    return prospects
