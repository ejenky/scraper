"""Follow-up scheduler: find emails due for follow-up and generate next step."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from outreach.config import FOLLOWUP_DAYS
from outreach.generator import generate_email
from outreach.models import EmailRecord, EmailStatus, SequenceStep
from outreach.storage import connect, save_email

# Defines the chain: current step -> next step to generate
_NEXT_STEP: dict[str, str] = {
    SequenceStep.INITIAL.value: SequenceStep.FOLLOWUP_1.value,
    SequenceStep.FOLLOWUP_1.value: SequenceStep.FOLLOWUP_2.value,
    SequenceStep.FOLLOWUP_2.value: SequenceStep.FOLLOWUP_3.value,
}

# Days after SENT to trigger each next step
_TRIGGER_DAYS: dict[str, int] = {
    SequenceStep.INITIAL.value: FOLLOWUP_DAYS["followup_1"],
    SequenceStep.FOLLOWUP_1.value: FOLLOWUP_DAYS["followup_2"] - FOLLOWUP_DAYS["followup_1"],
    SequenceStep.FOLLOWUP_2.value: FOLLOWUP_DAYS["followup_3"] - FOLLOWUP_DAYS["followup_2"],
}


def _prospect_dict(email: EmailRecord) -> dict:
    return {
        "company_name": email.prospect_company,
        "vertical": email.prospect_vertical,
        "website": email.prospect_website,
        "description": email.prospect_description,
        "contact_1_name": email.prospect_contact_name,
        "contact_1_title": email.prospect_contact_title,
        "has_affiliate_program": "unknown",
    }


def find_due_followups(campaign_id: Optional[str] = None) -> list[EmailRecord]:
    """Return EmailRecords whose follow-up step is due today (or overdue)."""
    from outreach.storage import _row_to_email  # noqa

    conn = connect()
    try:
        params: list = []
        q = """SELECT * FROM emails
               WHERE status IN ('sent','opened','clicked')
               AND sequence_step IN ('initial','followup_1','followup_2')
               AND sent_at IS NOT NULL"""
        if campaign_id:
            q += " AND campaign_id = ?"
            params.append(campaign_id)
        rows = conn.execute(q, params).fetchall()

        due: list[EmailRecord] = []
        now = datetime.now()
        for row in rows:
            e = _row_to_email(row)
            if e.status == EmailStatus.REPLIED:
                continue
            # Skip if this prospect already has a newer step queued/sent
            existing = conn.execute(
                """SELECT sequence_step FROM emails
                   WHERE prospect_email = ? AND campaign_id = ?
                   AND sequence_step = ?""",
                (e.prospect_email, e.campaign_id, _NEXT_STEP.get(e.sequence_step.value, "")),
            ).fetchone()
            if existing:
                continue

            trigger_days = _TRIGGER_DAYS.get(e.sequence_step.value, 0)
            if trigger_days <= 0:
                continue
            if e.sent_at and (now - e.sent_at) >= timedelta(days=trigger_days):
                due.append(e)
        return due
    finally:
        conn.close()


def generate_followup(email: EmailRecord) -> EmailRecord:
    """Generate a follow-up EmailRecord from a previous step email."""
    next_step = _NEXT_STEP.get(email.sequence_step.value)
    if not next_step:
        raise ValueError(f"No follow-up step after {email.sequence_step.value}")

    content = generate_email(_prospect_dict(email), step=next_step)

    # Threading: follow-ups should reply in the same thread
    new_subject = content["subject"]
    if not new_subject.lower().startswith("re:"):
        original_subject = email.subject.replace("Re: ", "").strip()
        new_subject = f"Re: {original_subject}"

    references = (email.references + " " if email.references else "") + (email.message_id or "")
    references = references.strip()

    new_email = EmailRecord(
        campaign_id=email.campaign_id,
        prospect_company=email.prospect_company,
        prospect_email=email.prospect_email,
        prospect_vertical=email.prospect_vertical,
        prospect_website=email.prospect_website,
        prospect_description=email.prospect_description,
        prospect_score=email.prospect_score,
        prospect_contact_name=email.prospect_contact_name,
        prospect_contact_title=email.prospect_contact_title,
        subject=new_subject,
        body_html=content["body_html"],
        body_text=content["body_text"],
        sequence_step=SequenceStep(next_step),
        parent_email_id=email.id,
        references=references,
        status=EmailStatus.QUEUED,
    )
    return new_email


def queue_due_followups(campaign_id: Optional[str] = None) -> list[EmailRecord]:
    """Find due follow-ups, generate them, save as QUEUED. Returns queued emails."""
    due = find_due_followups(campaign_id)
    logger.info(f"Found {len(due)} emails due for follow-up")
    queued: list[EmailRecord] = []
    conn = connect()
    try:
        for e in due:
            try:
                fu = generate_followup(e)
                save_email(conn, fu)
                queued.append(fu)
                logger.info(
                    f"Queued {fu.sequence_step.value} for {fu.prospect_email} "
                    f"({fu.prospect_company})"
                )
            except Exception as ex:
                logger.warning(f"Failed to generate follow-up for {e.prospect_email}: {ex}")
    finally:
        conn.close()
    return queued
