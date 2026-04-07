"""AI email generation via Groq (Llama 3.1). Falls back to template mode if no API key."""
from __future__ import annotations

import random
import re
import time

from loguru import logger

from outreach.config import GROQ_API_KEY, has_groq
from outreach.templates import (
    SYSTEM_PROMPT,
    build_followup_prompt,
    build_initial_prompt,
    clean_body,
    clean_subject,
    random_signoff,
    text_to_html,
    word_count,
)

try:
    from groq import Groq
    _HAS_GROQ = True
except Exception:  # pragma: no cover
    Groq = None  # type: ignore
    _HAS_GROQ = False


GROQ_MODEL = "llama-3.1-70b-versatile"
GROQ_CALL_DELAY_SECONDS = 2  # free tier: 30 req/min


def _parse_response(text: str) -> tuple[str, str]:
    """Extract SUBJECT: and BODY: from the LLM response."""
    subject = ""
    body = ""
    if "SUBJECT:" in text and "BODY:" in text:
        subject = text.split("SUBJECT:", 1)[1].split("BODY:", 1)[0].strip()
        body = text.split("BODY:", 1)[1].strip()
    else:
        lines = [l for l in text.strip().split("\n") if l.strip()]
        if lines:
            subject = re.sub(r"^(subject:|re:)\s*", "", lines[0], flags=re.IGNORECASE).strip()
            body = "\n".join(lines[1:]).strip()
    return clean_subject(subject), clean_body(body)


def _fallback_template(prospect: dict, step: str = "initial") -> tuple[str, str]:
    """Rule-based fallback when no Groq key is configured. Not as good as LLM but functional."""
    company = prospect.get("company_name", "there").strip() or "there"
    vertical = (prospect.get("vertical") or "your space").replace("_", " ")
    contact = (prospect.get("contact_1_name") or "").split()[0] if prospect.get("contact_1_name") else ""
    greeting = f"Hi {contact}," if contact else "Hi there,"

    if step == "initial":
        subject_options = [
            f"Quick idea for {company}",
            f"{company} + influencer marketing",
            f"Partnership idea for {company}",
        ]
        subject = random.choice(subject_options)
        body = (
            f"{greeting}\n\n"
            f"Noticed {company} is building in the {vertical} space. "
            f"I run Rocket Brands Media — we handle influencer and social campaigns "
            f"across a 700M+ follower network and specialize in {vertical} brands. "
            f"Worth a 15-minute call to see if there's a fit?\n\n"
            f"{random_signoff()}"
        )
    elif step == "followup_1":
        subject = f"Re: quick idea for {company}"
        body = (
            f"{greeting}\n\n"
            f"Just bumping this back up — did you get a chance to look?\n\n"
            f"{random_signoff()}"
        )
    elif step == "followup_2":
        subject = f"{vertical} case study"
        body = (
            f"{greeting}\n\n"
            f"We recently ran a campaign for another {vertical} brand and 4x'd their "
            f"installs in under 30 days. Happy to share the deck if it's useful for {company}.\n\n"
            f"{random_signoff()}"
        )
    else:  # followup_3
        subject = "Closing the loop"
        body = (
            f"{greeting}\n\n"
            f"I'll stop reaching out after this one — if influencer campaigns ever become "
            f"a priority for {company}, feel free to reply and we'll pick it up then.\n\n"
            f"{random_signoff()}"
        )
    return subject, body


def generate_email(prospect: dict, step: str = "initial") -> dict:
    """Generate a personalized email for a prospect.

    Returns {'subject': str, 'body_text': str, 'body_html': str}.
    Uses Groq if GROQ_API_KEY is set, otherwise falls back to templates.
    """
    subject = ""
    body = ""

    if has_groq() and _HAS_GROQ:
        try:
            if step == "initial":
                user_prompt = build_initial_prompt(prospect)
            else:
                user_prompt = build_followup_prompt(step, prospect)

            if user_prompt:
                client = Groq(api_key=GROQ_API_KEY)
                response = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.8,
                    max_tokens=300,
                    top_p=0.9,
                )
                text = response.choices[0].message.content or ""
                subject, body = _parse_response(text)
                time.sleep(GROQ_CALL_DELAY_SECONDS)  # rate-limit the free tier
        except Exception as e:
            logger.warning(f"Groq generation failed for {prospect.get('company_name')}: {e}")

    if not subject or not body:
        subject, body = _fallback_template(prospect, step=step)

    # Post-process
    subject = clean_subject(subject)
    body = clean_body(body)

    # Ensure the body ends with a signoff — LLM sometimes omits it
    if not re.search(r"\n(cheers|best|thanks|talk soon)[,!]?\n", body.lower()):
        body = body.rstrip() + "\n\n" + random_signoff()

    # Word count sanity: trim if too long
    if word_count(body) > 160:
        # Keep first 6 non-empty lines
        lines = [l for l in body.split("\n") if l.strip() or l == ""]
        body = "\n".join(lines[:12]).strip()

    html = text_to_html(body)
    return {"subject": subject, "body_text": body, "body_html": html}
