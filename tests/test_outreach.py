from datetime import datetime, timedelta
from pathlib import Path

import pytest

from outreach.models import EmailRecord, EmailStatus, SequenceStep
from outreach.templates import (
    apply_spintax,
    clean_body,
    clean_subject,
    text_to_html,
    validate_subject,
    word_count,
)


def test_spintax_basic():
    out = apply_spintax("{Hi|Hey|Hello} there")
    assert out in ("Hi there", "Hey there", "Hello there")


def test_spintax_nested_handles_repeat():
    # No infinite loop on plain text
    out = apply_spintax("no spintax here")
    assert out == "no spintax here"


def test_clean_subject_strips_quotes():
    assert clean_subject('"Hello world!"') == "Hello world"


def test_validate_subject_rejects_all_caps():
    ok, _ = validate_subject("HUGE DEAL INSIDE")
    assert not ok


def test_validate_subject_accepts_normal():
    ok, cleaned = validate_subject("Quick idea for Stake")
    assert ok
    assert "Stake" in cleaned


def test_validate_subject_rejects_long():
    ok, _ = validate_subject("one two three four five six seven eight nine ten eleven twelve")
    assert not ok


def test_validate_subject_rejects_bangs():
    ok, _ = validate_subject("Amazing deal!")
    assert not ok


def test_word_count():
    assert word_count("one two three") == 3
    assert word_count("") == 0


def test_clean_body_strips_html():
    body = "**Hey there**\n\n<p>Paragraph</p>\n\n\n\nToo much whitespace"
    out = clean_body(body)
    assert "<p>" not in out
    assert "**" not in out


def test_text_to_html_escapes():
    html = text_to_html("Hi <script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_outreach_storage_roundtrip(tmp_path, monkeypatch):
    # Point storage at a temp DB
    db = tmp_path / "outreach.db"
    monkeypatch.setattr("outreach.config.OUTREACH_DB", db)
    import importlib
    import outreach.storage as storage
    importlib.reload(storage)

    conn = storage.connect(db)
    camp = storage.create_campaign(conn, "Test Campaign", vertical="casino")
    assert camp.id

    email = EmailRecord(
        campaign_id=camp.id,
        prospect_company="Stake",
        prospect_email="hello@stake.com",
        prospect_vertical="casino",
        subject="Quick idea for Stake",
        body_text="Hi there,\n\nQuick test.\n\nCheers,\nEric",
        body_html="<p>Hi</p>",
        prospect_score=85,
    )
    storage.save_email(conn, email)
    emails = storage.emails_by_campaign(conn, camp.id)
    assert len(emails) == 1
    assert emails[0].prospect_company == "Stake"

    # Unsubscribe
    storage.add_unsubscribe(conn, "hello@stake.com")
    assert storage.is_unsubscribed(conn, "hello@stake.com")

    # Rate limit tracking
    storage.log_send(conn, "eric@llc.com")
    storage.log_send(conn, "eric@llc.com")
    assert storage.sends_today(conn, "eric@llc.com") == 2

    conn.close()


def test_generator_fallback_no_groq(monkeypatch):
    """Without a Groq key, generator falls back to the template and still produces output."""
    monkeypatch.setattr("outreach.generator.has_groq", lambda: False)
    from outreach.generator import generate_email
    result = generate_email({
        "company_name": "Stake",
        "vertical": "casino",
        "website": "https://stake.com",
        "description": "Online casino",
        "contact_1_name": "Ed Craven",
        "contact_1_title": "CEO",
    })
    assert result["subject"]
    assert result["body_text"]
    assert result["body_html"]
    assert "Stake" in result["body_text"] or "Stake" in result["subject"]
