"""Industry directory scrapers using AutoScraper for learn-by-example parsing."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import MODELS_DIR
from core.browser import fetch
from core.deduplication import normalize_domain
from core.models import Prospect, Source, Vertical

try:
    from autoscraper import AutoScraper  # type: ignore
    _HAS_AUTO = True
except Exception:  # pragma: no cover
    _HAS_AUTO = False
    AutoScraper = None  # type: ignore


def _model_path(url: str) -> Path:
    slug = normalize_domain(url).replace(".", "_")
    return MODELS_DIR / f"{slug}.json"


def scrape_directory(
    url: str,
    example: str,
    vertical: Vertical,
    use_cache: bool = True,
) -> list[Prospect]:
    """Scrape a directory page by teaching AutoScraper one example string."""
    if not _HAS_AUTO:
        logger.warning("autoscraper not installed; skipping directory source")
        return []

    model_file = _model_path(url)
    scraper = AutoScraper()

    results: list[str] = []
    if use_cache and model_file.exists():
        try:
            scraper.load(str(model_file))
            results = scraper.get_result_similar(url) or []
        except Exception as e:
            logger.debug(f"AutoScraper load/reuse failed: {e}")

    if not results:
        try:
            results = scraper.build(url, [example]) or []
            scraper.save(str(model_file))
        except Exception as e:
            logger.warning(f"AutoScraper build failed for {url}: {e}")
            return []

    prospects: list[Prospect] = []
    seen: set[str] = set()
    for item in results:
        name = (item or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        prospects.append(Prospect(
            company_name=name,
            vertical=vertical,
            source=Source.DIRECTORY,
            source_query=url,
        ))

    logger.info(f"Directory {url} -> {len(prospects)} names")
    return prospects


def scrape_directory_simple(url: str, vertical: Vertical) -> list[Prospect]:
    """Fallback: just pull all outbound links from a directory page."""
    page = fetch(url)
    if page is None:
        return []
    html = getattr(page, "html_content", "") or ""
    import re
    links = re.findall(r'href="(https?://[^"]+)"', html)
    seen: set[str] = set()
    prospects: list[Prospect] = []
    for link in links:
        domain = normalize_domain(link)
        if not domain or domain in seen:
            continue
        seen.add(domain)
        prospects.append(Prospect(
            company_name=domain.split(".")[0].title(),
            domain=domain,
            website=f"https://{domain}",
            vertical=vertical,
            source=Source.DIRECTORY,
            source_query=url,
        ))
    logger.info(f"Directory-simple {url} -> {len(prospects)} outbound links")
    return prospects
