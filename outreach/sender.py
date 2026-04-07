"""Gmail SMTP sender with account rotation and hard-capped rate limiting."""
from __future__ import annotations

import asyncio
import random
import sqlite3
import time
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Optional

from loguru import logger

from outreach.config import (
    BUSINESS_DAYS,
    BUSINESS_HOUR_END,
    BUSINESS_HOUR_START,
    GMAIL_SMTP_HOST,
    GMAIL_SMTP_PORT,
    MAX_DELAY_BETWEEN_EMAILS,
    MAX_EMAILS_PER_DAY_PER_ACCOUNT,
    MAX_EMAILS_PER_HOUR_PER_ACCOUNT,
    MIN_DELAY_BETWEEN_EMAILS,
    GmailAccount,
    load_gmail_accounts,
)
from outreach.models import EmailRecord, EmailStatus
from outreach.storage import (
    add_bounce,
    connect,
    is_bounced,
    is_unsubscribed,
    log_send,
    sends_last_hour,
    sends_today,
    update_email_status,
)
from outreach.templates import (
    UNSUBSCRIBE_HTML,
    UNSUBSCRIBE_TEXT,
    text_to_html,
    validate_subject,
)

try:
    import aiosmtplib  # type: ignore
    _HAS_AIOSMTP = True
except Exception:  # pragma: no cover
    aiosmtplib = None  # type: ignore
    _HAS_AIOSMTP = False


def is_business_hours(now: Optional[datetime] = None) -> bool:
    now = now or datetime.now()
    if now.weekday() not in BUSINESS_DAYS:
        return False
    return BUSINESS_HOUR_START <= now.hour < BUSINESS_HOUR_END


def _build_message(
    account: GmailAccount,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str,
    *,
    include_tracking_pixel: bool = False,
    tracking_pixel_url: str = "",
    in_reply_to: str = "",
    references: str = "",
) -> tuple[MIMEMultipart, str]:
    """Build a MIMEMultipart email. Returns (msg, message_id)."""
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{account.display_name} <{account.email}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Reply-To"] = account.email
    msg["Date"] = formatdate(localtime=True)
    message_id = make_msgid(domain=account.email.split("@")[-1])
    msg["Message-ID"] = message_id
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    # Plain text — REQUIRED for deliverability
    text_body = (body_text or "").rstrip() + UNSUBSCRIBE_TEXT
    msg.attach(MIMEText(text_body, "plain", "utf-8"))

    # HTML version
    html_body = body_html or text_to_html(body_text or "")
    if include_tracking_pixel and tracking_pixel_url:
        html_body += (
            f'<img src="{tracking_pixel_url}" width="1" height="1" '
            'style="display:none" alt="" />'
        )
    html_body += UNSUBSCRIBE_HTML
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg, message_id


class GmailSender:
    """Account-rotating Gmail SMTP sender with hard-capped rate limiting.

    Enforces (at the code level, not configurable):
    - Max emails/day per account (<= 30, whatever lower value env specifies)
    - Max emails/hour per account
    - Min 2min / max 5min random delay between sends
    - Business hours only (8am-6pm Mon-Fri)
    - Skip unsubscribed, bounced, and invalid recipients
    - Plain text always included
    - Subject line validation
    - No tracking pixel on initial emails (only on follow-ups)
    """

    def __init__(self, accounts: Optional[list[GmailAccount]] = None) -> None:
        self.accounts = accounts or load_gmail_accounts()
        self._rr_index = 0
        if not self.accounts:
            logger.warning("GmailSender: no Gmail accounts configured in .env")

    def _pick_account(self, conn: sqlite3.Connection) -> Optional[GmailAccount]:
        """Round-robin pick next account that's under daily/hourly limits."""
        if not self.accounts:
            return None
        n = len(self.accounts)
        for _ in range(n):
            acct = self.accounts[self._rr_index % n]
            self._rr_index = (self._rr_index + 1) % n
            daily = sends_today(conn, acct.email)
            hourly = sends_last_hour(conn, acct.email)
            if daily < MAX_EMAILS_PER_DAY_PER_ACCOUNT and hourly < MAX_EMAILS_PER_HOUR_PER_ACCOUNT:
                return acct
            logger.debug(
                f"Account {acct.email} at cap (day={daily}, hour={hourly}); rotating"
            )
        return None

    async def send_one(
        self,
        conn: sqlite3.Connection,
        email: EmailRecord,
        *,
        tracking_base_url: str = "",
        enforce_business_hours: bool = True,
    ) -> dict:
        """Send a single EmailRecord. Updates status in DB."""
        # Hard checks
        if enforce_business_hours and not is_business_hours():
            return {"status": "skipped", "reason": "outside business hours"}

        recipient = (email.prospect_email or "").strip().lower()
        if not recipient or "@" not in recipient:
            update_email_status(conn, email.id, EmailStatus.FAILED, error="invalid email")
            return {"status": "failed", "reason": "invalid email"}

        if is_unsubscribed(conn, recipient):
            update_email_status(conn, email.id, EmailStatus.UNSUBSCRIBED)
            return {"status": "skipped", "reason": "unsubscribed"}

        if is_bounced(conn, recipient):
            update_email_status(conn, email.id, EmailStatus.BOUNCED, error="previously bounced")
            return {"status": "skipped", "reason": "previously bounced"}

        ok, detail = validate_subject(email.subject)
        if not ok:
            update_email_status(conn, email.id, EmailStatus.FAILED, error=f"bad subject: {detail}")
            return {"status": "failed", "reason": f"bad subject: {detail}"}

        account = self._pick_account(conn)
        if account is None:
            return {"status": "skipped", "reason": "all accounts at daily/hourly limit"}

        # Tracking pixel only on follow-ups, never on initial (deliverability)
        include_pixel = email.sequence_step.value != "initial"
        pixel_url = (
            f"{tracking_base_url.rstrip('/')}/t/{email.tracking_id}.png"
            if include_pixel and tracking_base_url and email.tracking_id
            else ""
        )

        msg, message_id = _build_message(
            account,
            recipient,
            email.subject,
            email.body_text,
            email.body_html,
            include_tracking_pixel=include_pixel,
            tracking_pixel_url=pixel_url,
            in_reply_to=email.references or "",
            references=email.references or "",
        )

        if not _HAS_AIOSMTP:
            return {"status": "failed", "reason": "aiosmtplib not installed"}

        try:
            await aiosmtplib.send(
                msg,
                hostname=GMAIL_SMTP_HOST,
                port=GMAIL_SMTP_PORT,
                username=account.email,
                password=account.password,
                start_tls=True,
                timeout=30,
            )
        except Exception as e:
            err = str(e)
            logger.warning(f"Send failed {recipient}: {err}")
            # Heuristic bounce detection
            if any(x in err.lower() for x in ("does not exist", "user unknown", "no such user", "recipient rejected")):
                add_bounce(conn, recipient, err)
                return {"status": "bounced", "reason": err}
            update_email_status(conn, email.id, EmailStatus.FAILED, error=err)
            return {"status": "failed", "reason": err}

        # Success
        now = datetime.now()
        log_send(conn, account.email)
        update_email_status(
            conn,
            email.id,
            EmailStatus.SENT,
            sent_at=now,
            sender_email=account.email,
            message_id=message_id,
        )
        logger.info(f"Sent to {recipient} via {account.email} ({email.subject!r})")
        return {"status": "sent", "sender": account.email, "message_id": message_id}

    async def send_batch(
        self,
        emails: list[EmailRecord],
        *,
        tracking_base_url: str = "",
        enforce_business_hours: bool = True,
        dry_run: bool = False,
    ) -> list[dict]:
        """Send a batch with random delays between each. Respects all limits."""
        results: list[dict] = []
        conn = connect()
        try:
            for i, email in enumerate(emails):
                if dry_run:
                    results.append({"status": "dry_run", "to": email.prospect_email, "subject": email.subject})
                    continue

                res = await self.send_one(
                    conn,
                    email,
                    tracking_base_url=tracking_base_url,
                    enforce_business_hours=enforce_business_hours,
                )
                results.append(res)

                # Stop early if all accounts are exhausted
                if res.get("reason") == "all accounts at daily/hourly limit":
                    logger.info("All accounts at limit — stopping batch")
                    break

                # Random 2-5 min delay between sends
                if i < len(emails) - 1 and res.get("status") == "sent":
                    delay = random.uniform(MIN_DELAY_BETWEEN_EMAILS, MAX_DELAY_BETWEEN_EMAILS)
                    logger.debug(f"Sleeping {delay:.0f}s before next send")
                    await asyncio.sleep(delay)
        finally:
            conn.close()
        return results
