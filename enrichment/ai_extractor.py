"""AI extraction fallback using AutoScraper."""
from __future__ import annotations

from pathlib import Path

from loguru import logger

from config.settings import MODELS_DIR
from core.deduplication import normalize_domain

try:
    from autoscraper import AutoScraper  # type: ignore
    _HAS_AUTO = True
except Exception:  # pragma: no cover
    _HAS_AUTO = False
    AutoScraper = None  # type: ignore


def learn_and_extract(url: str, example: str, save_model: bool = True) -> list[str]:
    """Teach AutoScraper from one example; return all similar matches."""
    if not _HAS_AUTO:
        logger.warning("autoscraper not installed; ai_extractor disabled")
        return []
    scraper = AutoScraper()
    try:
        results = scraper.build(url, [example]) or []
    except Exception as e:
        logger.warning(f"AutoScraper build failed for {url}: {e}")
        return []
    if save_model:
        slug = normalize_domain(url).replace(".", "_")
        model_file = Path(MODELS_DIR) / f"{slug}.json"
        try:
            scraper.save(str(model_file))
        except Exception:
            pass
    return list(dict.fromkeys(results))


def apply_saved_model(url: str, model_slug: str) -> list[str]:
    if not _HAS_AUTO:
        return []
    model_file = Path(MODELS_DIR) / f"{model_slug}.json"
    if not model_file.exists():
        return []
    scraper = AutoScraper()
    try:
        scraper.load(str(model_file))
        return scraper.get_result_similar(url) or []
    except Exception as e:
        logger.debug(f"AutoScraper load failed: {e}")
        return []
