"""Google Play Store scraper — finds publishers via app search."""
from __future__ import annotations

from loguru import logger

from config.settings import MAX_DESCRIPTION_CHARS
from core.deduplication import normalize_domain
from core.models import Prospect, Source, Vertical

try:
    from google_play_scraper import app as play_app
    from google_play_scraper import search as play_search
    _HAS_GPS = True
except Exception:  # pragma: no cover
    _HAS_GPS = False


def _classify_vertical(category: str, query: str, title: str) -> Vertical:
    blob = f"{category} {query} {title}".lower()
    if any(k in blob for k in ("casino", "slots", "poker", "baccarat", "roulette")):
        return Vertical.CASINO
    if any(k in blob for k in ("sportsbook", "sports bet", "betting")):
        return Vertical.SPORTS_BETTING
    if any(k in blob for k in ("crypto", "web3", "nft", "blockchain", "bitcoin")):
        return Vertical.CRYPTO
    if any(k in blob for k in ("fantasy",)):
        return Vertical.FANTASY_SPORTS
    if any(k in blob for k in ("prediction",)):
        return Vertical.PREDICTION_MARKETS
    if any(k in blob for k in ("esport",)):
        return Vertical.ESPORTS
    if "game" in blob:
        return Vertical.MOBILE_GAMES
    return Vertical.APPS


def discover(query: str, num: int = 30, vertical: Vertical | None = None) -> list[Prospect]:
    """Search Play Store and extract publisher info."""
    if not _HAS_GPS:
        logger.warning("google-play-scraper not installed; skipping Play Store source")
        return []

    try:
        results = play_search(query, n_hits=num, lang="en", country="us")
    except Exception as e:
        logger.warning(f"Play Store search failed for '{query}': {e}")
        return []

    prospects: list[Prospect] = []
    seen_devs: set[str] = set()

    for r in results:
        dev = (r.get("developer") or "").strip()
        if not dev or dev in seen_devs:
            continue
        seen_devs.add(dev)

        app_id = r.get("appId", "")
        details: dict = {}
        if app_id:
            try:
                details = play_app(app_id) or {}
            except Exception as e:
                logger.debug(f"Play app() failed for {app_id}: {e}")
                details = r  # fallback to search result

        website = details.get("developerWebsite", "") or ""
        domain = normalize_domain(website) if website else ""

        v = vertical or _classify_vertical(
            details.get("genre", "") or "",
            query,
            details.get("title", "") or "",
        )

        p = Prospect(
            company_name=dev,
            website=website,
            domain=domain,
            vertical=v,
            source=Source.GOOGLE_PLAY,
            source_query=query,
            developer_name=dev,
            developer_email=details.get("developerEmail", "") or "",
            app_name=details.get("title", "") or r.get("title", ""),
            app_id=app_id,
            installs=details.get("installs", "") or "",
            app_rating=float(details.get("score") or 0) or 0.0,
            description=(details.get("summary") or details.get("description") or "")[:MAX_DESCRIPTION_CHARS],
        )
        if p.developer_email:
            p.primary_email = p.developer_email
            if p.developer_email not in p.all_emails:
                p.all_emails.append(p.developer_email)
        prospects.append(p)

    logger.info(f"Play Store '{query}' -> {len(prospects)} publishers")
    return prospects
