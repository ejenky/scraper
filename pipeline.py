"""Main orchestration pipeline: discover + enrich + score + save."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from loguru import logger

from config.settings import BATCH_SIZE, DEFAULT_CSV, LOGS_DIR
from config.verticals import VERTICALS
from core.deduplication import Deduplicator
from core.models import Prospect, Source, Vertical
from core.storage import load_csv, save_csv
from sources import google_maps, google_play, google_search
from sources import linkedin as linkedin_src
from sources import website as website_src

logger.add(LOGS_DIR / "scraper_{time}.log", rotation="10 MB", retention="7 days")


# --- Scoring ---

def score_prospect(p: Prospect) -> int:
    score = 0

    if p.primary_email:
        score += 20
    if len(p.all_emails) > 1:
        score += 5

    partnership_kw = ("partner", "affiliate", "marketing", "media", "advertis")
    if p.primary_email and any(kw in p.primary_email.lower() for kw in partnership_kw):
        score += 15

    if p.has_affiliate_program:
        score += 20

    if p.contacts:
        score += 10
    if any(
        ("cmo" in c.title.lower() or "head of" in c.title.lower() or "vp " in c.title.lower())
        for c in p.contacts
    ):
        score += 10

    if p.socials.linkedin:
        score += 5
    score += min(p.socials.count() * 3, 15)

    if p.developer_email:
        score += 10
    if p.installs and any(x in p.installs for x in ("1,000,000", "5,000,000", "10,000,000", "100,000,000")):
        score += 10

    if p.maps_reviews_count > 50:
        score += 5

    return min(score, 100)


# --- Discovery ---

def discover_vertical(
    vertical: str,
    pages: int = 2,
    use_maps: bool = True,
    use_play: bool = True,
    use_search: bool = True,
) -> list[Prospect]:
    """Run all discovery sources for a single vertical."""
    if vertical not in VERTICALS:
        raise ValueError(f"Unknown vertical: {vertical}")
    cfg = VERTICALS[vertical]
    v_enum = Vertical(vertical)
    results: list[Prospect] = []

    if use_search:
        for q in cfg["queries"]:
            try:
                results.extend(google_search.discover(q, v_enum, num_results=pages * 10))
            except Exception as e:
                logger.warning(f"google_search error '{q}': {e}")

    if use_maps:
        for q in cfg.get("maps_queries", []):
            try:
                results.extend(google_maps.discover(q, v_enum))
            except Exception as e:
                logger.warning(f"google_maps error '{q}': {e}")

    if use_play:
        for q in cfg.get("play_store_queries", []):
            try:
                results.extend(google_play.discover(q, num=30, vertical=v_enum))
            except Exception as e:
                logger.warning(f"google_play error '{q}': {e}")

    return results


def discover_all(pages: int = 2, **kwargs) -> list[Prospect]:
    out: list[Prospect] = []
    for v in VERTICALS.keys():
        logger.info(f"=== Discovering vertical: {v} ===")
        out.extend(discover_vertical(v, pages=pages, **kwargs))
    return out


# --- Enrichment ---

def enrich_prospects(
    prospects: Iterable[Prospect],
    deep_web: bool = True,
    use_linkedin: bool = False,
) -> list[Prospect]:
    from datetime import datetime

    enriched: list[Prospect] = []
    for p in prospects:
        try:
            if deep_web and (p.website or p.domain):
                website_src.enrich_prospect(p, deep=True)
            if use_linkedin and p.socials.linkedin:
                linkedin_src.enrich(p)
            p.score = score_prospect(p)
            p.enriched = True
            p.enriched_at = datetime.now()
            enriched.append(p)
        except Exception as e:
            logger.warning(f"Enrich failed for {p.company_name}: {e}")
            enriched.append(p)
    return enriched


# --- Full pipeline ---

def run_discovery(
    vertical: str = "all",
    pages: int = 2,
    output: Optional[Path] = None,
    enrich: bool = True,
    use_linkedin: bool = False,
    max_prospects: Optional[int] = None,
) -> list[Prospect]:
    """Full discovery pipeline. Dedup against existing CSV, enrich, save."""
    output = Path(output or DEFAULT_CSV)

    dedup = Deduplicator()
    existing = load_csv(output)
    dedup.seed(existing)
    logger.info(f"Seeded deduplicator with {len(existing)} existing prospects")

    raw: list[Prospect] = []
    if vertical == "all":
        raw = discover_all(pages=pages)
    else:
        raw = discover_vertical(vertical, pages=pages)

    # Dedup — append the actual prospect `p` (not the merged return value,
    # which could be an already-stored record being merged into).
    new_prospects: list[Prospect] = []
    for p in raw:
        if dedup.contains(p):
            continue
        dedup.add(p)
        new_prospects.append(p)
        if max_prospects and len(new_prospects) >= max_prospects:
            break

    logger.info(f"Discovered {len(new_prospects)} new prospects (from {len(raw)} raw)")

    def _persist() -> None:
        """Write existing + new_prospects to the CSV as a single authoritative snapshot."""
        save_csv(output, existing + new_prospects)

    # Enrich in batches, persisting a full snapshot after each batch so we
    # never lose data on crash — and always end with a final save_csv.
    if enrich and new_prospects:
        for i in range(0, len(new_prospects), BATCH_SIZE):
            batch = new_prospects[i : i + BATCH_SIZE]
            enrich_prospects(batch, deep_web=True, use_linkedin=use_linkedin)
            _persist()
    else:
        for p in new_prospects:
            p.score = score_prospect(p)

    # Final save — ensures the complete deduped dataset (existing + newly
    # discovered, scored) is written regardless of enrichment path taken.
    _persist()
    logger.info(
        f"Saved {len(existing) + len(new_prospects)} total prospects to {output} "
        f"({len(new_prospects)} new this run)"
    )

    return new_prospects
