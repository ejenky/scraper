"""SQLite storage for campaigns, emails, tracking events, and unsubscribes."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from outreach.config import OUTREACH_DB
from outreach.models import (
    Campaign,
    CampaignStatus,
    EmailRecord,
    EmailStatus,
    SequenceStep,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    vertical TEXT DEFAULT 'all',
    status TEXT DEFAULT 'draft',
    created_at TEXT,
    total_emails INTEGER DEFAULT 0,
    sent_count INTEGER DEFAULT 0,
    open_count INTEGER DEFAULT 0,
    click_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    bounce_count INTEGER DEFAULT 0,
    unsubscribe_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS emails (
    id TEXT PRIMARY KEY,
    campaign_id TEXT,
    prospect_company TEXT,
    prospect_email TEXT,
    prospect_vertical TEXT,
    prospect_website TEXT,
    prospect_description TEXT,
    prospect_score INTEGER DEFAULT 0,
    prospect_contact_name TEXT,
    prospect_contact_title TEXT,
    subject TEXT,
    body_html TEXT,
    body_text TEXT,
    sender_email TEXT,
    sequence_step TEXT DEFAULT 'initial',
    parent_email_id TEXT,
    message_id TEXT,
    references_header TEXT,
    status TEXT DEFAULT 'draft',
    sent_at TEXT,
    opened_at TEXT,
    opened_count INTEGER DEFAULT 0,
    clicked_at TEXT,
    clicked_count INTEGER DEFAULT 0,
    replied_at TEXT,
    error TEXT,
    tracking_id TEXT UNIQUE,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_emails_campaign ON emails(campaign_id);
CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);
CREATE INDEX IF NOT EXISTS idx_emails_tracking ON emails(tracking_id);
CREATE INDEX IF NOT EXISTS idx_emails_prospect ON emails(prospect_email);

CREATE TABLE IF NOT EXISTS tracking_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tracking_id TEXT,
    event_type TEXT,
    ip TEXT,
    user_agent TEXT,
    timestamp TEXT,
    metadata TEXT
);
CREATE INDEX IF NOT EXISTS idx_tracking_id ON tracking_events(tracking_id);

CREATE TABLE IF NOT EXISTS unsubscribes (
    email TEXT PRIMARY KEY,
    unsubscribed_at TEXT
);

CREATE TABLE IF NOT EXISTS bounces (
    email TEXT PRIMARY KEY,
    bounced_at TEXT,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS send_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_email TEXT,
    sent_at TEXT,
    date TEXT
);
CREATE INDEX IF NOT EXISTS idx_send_log_date ON send_log(sender_email, date);
"""


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def connect(db_path: Path = OUTREACH_DB) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


# --- Campaign CRUD ---

def create_campaign(conn: sqlite3.Connection, name: str, vertical: str = "all") -> Campaign:
    c = Campaign(id=str(uuid.uuid4()), name=name, vertical=vertical)
    conn.execute(
        """INSERT INTO campaigns (id, name, vertical, status, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (c.id, c.name, c.vertical, c.status.value, c.created_at.isoformat()),
    )
    conn.commit()
    logger.info(f"Created campaign {c.name} ({c.id[:8]})")
    return c


def get_campaign(conn: sqlite3.Connection, identifier: str) -> Optional[Campaign]:
    """Look up a campaign by id OR name."""
    row = conn.execute(
        "SELECT * FROM campaigns WHERE id = ? OR name = ? LIMIT 1",
        (identifier, identifier),
    ).fetchone()
    if not row:
        return None
    return _row_to_campaign(row)


def list_campaigns(conn: sqlite3.Connection) -> list[Campaign]:
    rows = conn.execute("SELECT * FROM campaigns ORDER BY created_at DESC").fetchall()
    return [_row_to_campaign(r) for r in rows]


def update_campaign_counts(conn: sqlite3.Connection, campaign_id: str) -> None:
    """Recalculate campaign aggregate counts from emails table."""
    stats = conn.execute(
        """SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status IN ('sent','opened','clicked','replied') THEN 1 ELSE 0 END) AS sent,
            SUM(CASE WHEN opened_count > 0 THEN 1 ELSE 0 END) AS opened,
            SUM(CASE WHEN clicked_count > 0 THEN 1 ELSE 0 END) AS clicked,
            SUM(CASE WHEN status = 'replied' THEN 1 ELSE 0 END) AS replied,
            SUM(CASE WHEN status = 'bounced' THEN 1 ELSE 0 END) AS bounced,
            SUM(CASE WHEN status = 'unsubscribed' THEN 1 ELSE 0 END) AS unsubscribed
           FROM emails WHERE campaign_id = ?""",
        (campaign_id,),
    ).fetchone()
    if not stats:
        return
    conn.execute(
        """UPDATE campaigns SET
               total_emails = ?,
               sent_count = ?,
               open_count = ?,
               click_count = ?,
               reply_count = ?,
               bounce_count = ?,
               unsubscribe_count = ?
           WHERE id = ?""",
        (
            stats["total"] or 0,
            stats["sent"] or 0,
            stats["opened"] or 0,
            stats["clicked"] or 0,
            stats["replied"] or 0,
            stats["bounced"] or 0,
            stats["unsubscribed"] or 0,
            campaign_id,
        ),
    )
    conn.commit()


def _row_to_campaign(row: sqlite3.Row) -> Campaign:
    return Campaign(
        id=row["id"],
        name=row["name"],
        vertical=row["vertical"] or "all",
        status=CampaignStatus(row["status"] or "draft"),
        created_at=_parse_dt(row["created_at"]) or datetime.now(),
        total_emails=row["total_emails"] or 0,
        sent_count=row["sent_count"] or 0,
        open_count=row["open_count"] or 0,
        click_count=row["click_count"] or 0,
        reply_count=row["reply_count"] or 0,
        bounce_count=row["bounce_count"] or 0,
        unsubscribe_count=(row["unsubscribe_count"] if "unsubscribe_count" in row.keys() else 0) or 0,
    )


# --- Email CRUD ---

def save_email(conn: sqlite3.Connection, email: EmailRecord) -> EmailRecord:
    if not email.id:
        email.id = str(uuid.uuid4())
    if not email.tracking_id:
        email.tracking_id = uuid.uuid4().hex
    conn.execute(
        """INSERT OR REPLACE INTO emails (
            id, campaign_id, prospect_company, prospect_email, prospect_vertical,
            prospect_website, prospect_description, prospect_score,
            prospect_contact_name, prospect_contact_title,
            subject, body_html, body_text, sender_email, sequence_step,
            parent_email_id, message_id, references_header,
            status, sent_at, opened_at, opened_count, clicked_at, clicked_count,
            replied_at, error, tracking_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            email.id, email.campaign_id, email.prospect_company, email.prospect_email,
            email.prospect_vertical, email.prospect_website, email.prospect_description,
            email.prospect_score, email.prospect_contact_name, email.prospect_contact_title,
            email.subject, email.body_html, email.body_text, email.sender_email,
            email.sequence_step.value, email.parent_email_id, email.message_id,
            email.references, email.status.value, _iso(email.sent_at), _iso(email.opened_at),
            email.opened_count, _iso(email.clicked_at), email.clicked_count,
            _iso(email.replied_at), email.error, email.tracking_id, email.created_at.isoformat(),
        ),
    )
    conn.commit()
    return email


def _row_to_email(row: sqlite3.Row) -> EmailRecord:
    keys = row.keys()
    return EmailRecord(
        id=row["id"],
        campaign_id=row["campaign_id"] or "",
        prospect_company=row["prospect_company"] or "",
        prospect_email=row["prospect_email"] or "",
        prospect_vertical=row["prospect_vertical"] or "",
        prospect_website=row["prospect_website"] or "",
        prospect_description=row["prospect_description"] or "",
        prospect_score=row["prospect_score"] or 0,
        prospect_contact_name=(row["prospect_contact_name"] if "prospect_contact_name" in keys else "") or "",
        prospect_contact_title=(row["prospect_contact_title"] if "prospect_contact_title" in keys else "") or "",
        subject=row["subject"] or "",
        body_html=row["body_html"] or "",
        body_text=row["body_text"] or "",
        sender_email=row["sender_email"] or "",
        sequence_step=SequenceStep(row["sequence_step"] or "initial"),
        parent_email_id=(row["parent_email_id"] if "parent_email_id" in keys else "") or "",
        message_id=(row["message_id"] if "message_id" in keys else "") or "",
        references=(row["references_header"] if "references_header" in keys else "") or "",
        status=EmailStatus(row["status"] or "draft"),
        sent_at=_parse_dt(row["sent_at"]),
        opened_at=_parse_dt(row["opened_at"]),
        opened_count=row["opened_count"] or 0,
        clicked_at=_parse_dt(row["clicked_at"]),
        clicked_count=row["clicked_count"] or 0,
        replied_at=_parse_dt(row["replied_at"]) if "replied_at" in keys else None,
        error=(row["error"] if "error" in keys else "") or "",
        tracking_id=row["tracking_id"] or "",
        created_at=_parse_dt(row["created_at"]) or datetime.now(),
    )


def get_email(conn: sqlite3.Connection, email_id: str) -> Optional[EmailRecord]:
    row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
    return _row_to_email(row) if row else None


def emails_by_campaign(
    conn: sqlite3.Connection,
    campaign_id: str,
    status: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[EmailRecord]:
    q = "SELECT * FROM emails WHERE campaign_id = ?"
    params: list = [campaign_id]
    if status:
        q += " AND status = ?"
        params.append(status)
    q += " ORDER BY created_at DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = conn.execute(q, params).fetchall()
    return [_row_to_email(r) for r in rows]


def update_email_status(
    conn: sqlite3.Connection,
    email_id: str,
    status: EmailStatus,
    sent_at: Optional[datetime] = None,
    sender_email: str = "",
    error: str = "",
    message_id: str = "",
) -> None:
    fields = ["status = ?"]
    params: list = [status.value]
    if sent_at is not None:
        fields.append("sent_at = ?")
        params.append(_iso(sent_at))
    if sender_email:
        fields.append("sender_email = ?")
        params.append(sender_email)
    if error:
        fields.append("error = ?")
        params.append(error)
    if message_id:
        fields.append("message_id = ?")
        params.append(message_id)
    params.append(email_id)
    conn.execute(f"UPDATE emails SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()


def mark_replied(conn: sqlite3.Connection, prospect_email: str) -> int:
    """Mark all emails to this prospect as replied. Returns row count."""
    now = datetime.now().isoformat()
    cur = conn.execute(
        """UPDATE emails SET status = 'replied', replied_at = ?
           WHERE prospect_email = ? AND status NOT IN ('replied','bounced','unsubscribed')""",
        (now, prospect_email.lower()),
    )
    conn.commit()
    return cur.rowcount or 0


# --- Unsubscribe / bounce ---

def add_unsubscribe(conn: sqlite3.Connection, email: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO unsubscribes (email, unsubscribed_at) VALUES (?, ?)",
        (email.lower(), datetime.now().isoformat()),
    )
    conn.execute(
        "UPDATE emails SET status = 'unsubscribed' WHERE prospect_email = ? AND status NOT IN ('replied')",
        (email.lower(),),
    )
    conn.commit()


def is_unsubscribed(conn: sqlite3.Connection, email: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM unsubscribes WHERE email = ?", (email.lower(),)
    ).fetchone()
    return row is not None


def add_bounce(conn: sqlite3.Connection, email: str, reason: str = "") -> None:
    conn.execute(
        "INSERT OR REPLACE INTO bounces (email, bounced_at, reason) VALUES (?, ?, ?)",
        (email.lower(), datetime.now().isoformat(), reason),
    )
    conn.execute(
        "UPDATE emails SET status = 'bounced', error = ? WHERE prospect_email = ?",
        (reason, email.lower()),
    )
    conn.commit()


def is_bounced(conn: sqlite3.Connection, email: str) -> bool:
    row = conn.execute("SELECT 1 FROM bounces WHERE email = ?", (email.lower(),)).fetchone()
    return row is not None


# --- Send log (daily rate limit) ---

def log_send(conn: sqlite3.Connection, sender_email: str) -> None:
    now = datetime.now()
    conn.execute(
        "INSERT INTO send_log (sender_email, sent_at, date) VALUES (?, ?, ?)",
        (sender_email, now.isoformat(), now.strftime("%Y-%m-%d")),
    )
    conn.commit()


def sends_today(conn: sqlite3.Connection, sender_email: str) -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM send_log WHERE sender_email = ? AND date = ?",
        (sender_email, today),
    ).fetchone()
    return row["n"] if row else 0


def sends_last_hour(conn: sqlite3.Connection, sender_email: str) -> int:
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM send_log WHERE sender_email = ? AND sent_at >= ?",
        (sender_email, cutoff),
    ).fetchone()
    return row["n"] if row else 0


# --- Tracking events ---

def log_event(
    conn: sqlite3.Connection,
    tracking_id: str,
    event_type: str,
    ip: str = "",
    user_agent: str = "",
    metadata: str = "",
) -> None:
    conn.execute(
        """INSERT INTO tracking_events (tracking_id, event_type, ip, user_agent, timestamp, metadata)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (tracking_id, event_type, ip, user_agent, datetime.now().isoformat(), metadata),
    )
    conn.commit()
