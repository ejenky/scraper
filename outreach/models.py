"""Pydantic models for the outreach system."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EmailStatus(str, Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    BOUNCED = "bounced"
    FAILED = "failed"
    UNSUBSCRIBED = "unsubscribed"


class SequenceStep(str, Enum):
    INITIAL = "initial"
    FOLLOWUP_1 = "followup_1"    # 3 days after initial
    FOLLOWUP_2 = "followup_2"    # 7 days after initial
    FOLLOWUP_3 = "followup_3"    # 14 days after initial (breakup)


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class EmailRecord(BaseModel):
    id: str = ""
    campaign_id: str = ""

    # Prospect snapshot
    prospect_company: str
    prospect_email: str
    prospect_vertical: str = ""
    prospect_website: str = ""
    prospect_description: str = ""
    prospect_score: int = 0
    prospect_contact_name: str = ""
    prospect_contact_title: str = ""

    # Email content
    subject: str
    body_html: str
    body_text: str  # Plain text version (REQUIRED for deliverability)

    # Sending info
    sender_email: str = ""
    sequence_step: SequenceStep = SequenceStep.INITIAL
    parent_email_id: str = ""  # For follow-ups — links to original email
    message_id: str = ""       # RFC Message-ID for threading
    references: str = ""       # References header for threading

    # Status
    status: EmailStatus = EmailStatus.DRAFT
    sent_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    opened_count: int = 0
    clicked_at: Optional[datetime] = None
    clicked_count: int = 0
    replied_at: Optional[datetime] = None
    error: str = ""

    # Tracking
    tracking_id: str = ""

    created_at: datetime = Field(default_factory=datetime.now)


class Campaign(BaseModel):
    id: str = ""
    name: str
    vertical: str = "all"
    status: CampaignStatus = CampaignStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.now)
    total_emails: int = 0
    sent_count: int = 0
    open_count: int = 0
    click_count: int = 0
    reply_count: int = 0
    bounce_count: int = 0
    unsubscribe_count: int = 0
