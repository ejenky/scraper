"""CSV / JSON / SQLite persistence for prospects."""
from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from loguru import logger

from core.models import ContactPerson, Prospect, SocialLinks, Source, Vertical

CSV_COLUMNS = [
    "company_name", "domain", "website", "vertical", "source", "source_query",
    "primary_email", "all_emails", "phone",
    "contact_1_name", "contact_1_title", "contact_1_email", "contact_1_linkedin",
    "contact_2_name", "contact_2_title", "contact_2_email", "contact_2_linkedin",
    "linkedin", "twitter", "instagram", "telegram", "discord",
    "facebook", "youtube", "tiktok",
    "description", "has_affiliate_program", "affiliate_url", "company_size",
    "app_name", "app_id", "developer_name", "developer_email", "installs", "app_rating",
    "maps_rating", "maps_reviews_count", "address", "maps_category",
    "score", "scraped_at", "enriched",
]


def _contact_at(contacts: list[ContactPerson], idx: int, field: str) -> str:
    if idx >= len(contacts):
        return ""
    c = contacts[idx]
    return getattr(c, field, "") or ""


def prospect_to_row(p: Prospect) -> dict[str, str]:
    row = {
        "company_name": p.company_name,
        "domain": p.domain,
        "website": p.website,
        "vertical": p.vertical.value,
        "source": p.source.value,
        "source_query": p.source_query,
        "primary_email": p.primary_email,
        "all_emails": ";".join(p.all_emails),
        "phone": p.phone,
        "description": p.description,
        "has_affiliate_program": "yes" if p.has_affiliate_program else "",
        "affiliate_url": p.affiliate_url,
        "company_size": p.company_size,
        "app_name": p.app_name,
        "app_id": p.app_id,
        "developer_name": p.developer_name,
        "developer_email": p.developer_email,
        "installs": p.installs,
        "app_rating": str(p.app_rating) if p.app_rating else "",
        "maps_rating": str(p.maps_rating) if p.maps_rating else "",
        "maps_reviews_count": str(p.maps_reviews_count) if p.maps_reviews_count else "",
        "address": p.address,
        "maps_category": p.maps_category,
        "score": str(p.score),
        "scraped_at": p.scraped_at.isoformat(),
        "enriched": "yes" if p.enriched else "",
    }
    for i in range(2):
        for field in ("name", "title", "email", "linkedin_url"):
            key_field = "linkedin" if field == "linkedin_url" else field
            row[f"contact_{i+1}_{key_field}"] = _contact_at(p.contacts, i, field)
    soc = p.socials.model_dump()
    for key in ("linkedin", "twitter", "instagram", "telegram", "discord",
                "facebook", "youtube", "tiktok"):
        row[key] = soc.get(key, "")
    return row


def row_to_prospect(row: dict[str, str]) -> Prospect:
    def _get(k: str, default: str = "") -> str:
        return (row.get(k) or default).strip()

    contacts: list[ContactPerson] = []
    for i in range(1, 3):
        name = _get(f"contact_{i}_name")
        if name:
            contacts.append(ContactPerson(
                name=name,
                title=_get(f"contact_{i}_title"),
                email=_get(f"contact_{i}_email"),
                linkedin_url=_get(f"contact_{i}_linkedin"),
            ))

    socials = SocialLinks(
        linkedin=_get("linkedin"),
        twitter=_get("twitter"),
        instagram=_get("instagram"),
        telegram=_get("telegram"),
        discord=_get("discord"),
        facebook=_get("facebook"),
        youtube=_get("youtube"),
        tiktok=_get("tiktok"),
    )

    try:
        vertical = Vertical(_get("vertical") or "unknown")
    except ValueError:
        vertical = Vertical.UNKNOWN
    try:
        source = Source(_get("source") or "manual")
    except ValueError:
        source = Source.MANUAL

    all_emails_raw = _get("all_emails")
    all_emails = [e for e in all_emails_raw.split(";") if e] if all_emails_raw else []

    scraped_at_raw = _get("scraped_at")
    try:
        scraped_at = datetime.fromisoformat(scraped_at_raw) if scraped_at_raw else datetime.now()
    except ValueError:
        scraped_at = datetime.now()

    def _float(k: str) -> float:
        try:
            return float(_get(k) or 0)
        except ValueError:
            return 0.0

    def _int(k: str) -> int:
        try:
            return int(float(_get(k) or 0))
        except ValueError:
            return 0

    return Prospect(
        company_name=_get("company_name"),
        domain=_get("domain"),
        website=_get("website"),
        vertical=vertical,
        source=source,
        source_query=_get("source_query"),
        primary_email=_get("primary_email"),
        all_emails=all_emails,
        phone=_get("phone"),
        contacts=contacts,
        socials=socials,
        description=_get("description"),
        has_affiliate_program=bool(_get("has_affiliate_program")),
        affiliate_url=_get("affiliate_url"),
        company_size=_get("company_size"),
        app_name=_get("app_name"),
        app_id=_get("app_id"),
        developer_name=_get("developer_name"),
        developer_email=_get("developer_email"),
        installs=_get("installs"),
        app_rating=_float("app_rating"),
        maps_rating=_float("maps_rating"),
        maps_reviews_count=_int("maps_reviews_count"),
        address=_get("address"),
        maps_category=_get("maps_category"),
        score=_int("score"),
        scraped_at=scraped_at,
        enriched=bool(_get("enriched")),
    )


def load_csv(path: Path) -> list[Prospect]:
    path = Path(path)
    if not path.exists():
        return []
    out: list[Prospect] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                out.append(row_to_prospect(row))
            except Exception as e:
                logger.warning(f"Skipping invalid row: {e}")
    logger.info(f"Loaded {len(out)} prospects from {path}")
    return out


def save_csv(path: Path, prospects: list[Prospect]) -> None:
    """Write full CSV (overwrites). Use append_csv for incremental."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for p in prospects:
            writer.writerow(prospect_to_row(p))
    logger.info(f"Saved {len(prospects)} prospects to {path}")


def append_csv(path: Path, prospects: list[Prospect]) -> None:
    """Append prospects to CSV, writing header if file doesn't exist."""
    if not prospects:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for p in prospects:
            writer.writerow(prospect_to_row(p))
    logger.info(f"Appended {len(prospects)} prospects to {path}")


def save_json(path: Path, prospects: list[Prospect]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [p.model_dump(mode="json") for p in prospects]
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    logger.info(f"Saved {len(prospects)} prospects to {path}")


# --- SQLite ---

def init_db(path: Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prospects (
            domain TEXT PRIMARY KEY,
            company_name TEXT,
            website TEXT,
            vertical TEXT,
            source TEXT,
            primary_email TEXT,
            data_json TEXT,
            score INTEGER,
            scraped_at TEXT,
            enriched INTEGER
        )
    """)
    conn.commit()
    return conn


def upsert_db(conn: sqlite3.Connection, prospects: list[Prospect]) -> None:
    rows = []
    for p in prospects:
        domain = p.domain or p.website or p.company_name
        rows.append((
            domain, p.company_name, p.website, p.vertical.value, p.source.value,
            p.primary_email, p.model_dump_json(), p.score,
            p.scraped_at.isoformat(), 1 if p.enriched else 0,
        ))
    conn.executemany("""
        INSERT INTO prospects (domain, company_name, website, vertical, source,
                               primary_email, data_json, score, scraped_at, enriched)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(domain) DO UPDATE SET
            company_name=excluded.company_name,
            website=excluded.website,
            vertical=excluded.vertical,
            primary_email=excluded.primary_email,
            data_json=excluded.data_json,
            score=excluded.score,
            enriched=excluded.enriched
    """, rows)
    conn.commit()
