"""Email templates, spintax, and deliverability helpers."""
from __future__ import annotations

import random
import re

SYSTEM_PROMPT = """You are a business development expert writing cold outreach emails for Rocket Brands Media, a social media marketing and influencer agency with a network of 700M+ followers across Instagram, Twitter, TikTok, and other platforms.

Your goal: Get the recipient to reply or book a call about a potential media buying / influencer marketing partnership.

RULES:
1. Keep emails SHORT — 4-6 sentences max, under 100 words. Nobody reads long cold emails.
2. Lead with something specific about THEIR company — show you researched them.
3. One clear value proposition tied to their business.
4. One simple call to action (reply or book a call).
5. NO generic filler phrases like "I hope this finds you well" or "I came across your company".
6. NO bullet points or lists — write like a human, conversational tone.
7. Sound like a real person, not a sales robot.
8. Subject line: short, specific, no clickbait, no ALL CAPS, no emojis.
9. NEVER mention that this is a mass email or automated.
10. Write in plain text style — no HTML formatting, no bold, no images.
"""


def build_initial_prompt(prospect: dict) -> str:
    vertical = (prospect.get("vertical") or "").replace("_", " ")
    return f"""Write a cold outreach email for this prospect:

Company: {prospect.get('company_name', '')}
Industry/Vertical: {vertical}
Website: {prospect.get('website', '')}
Description: {prospect.get('description', '')}
Has Affiliate Program: {prospect.get('has_affiliate_program', 'unknown')}
Contact Name: {prospect.get('contact_1_name') or 'the team'}
Contact Title: {prospect.get('contact_1_title', '')}

About us (Rocket Brands Media):
- Social media marketing & influencer agency
- Network of 700M+ followers across Instagram, Twitter, TikTok
- We drive user acquisition and brand awareness through influencer campaigns
- Specialize in {vertical} vertical

Generate:
1. A subject line (under 8 words)
2. The email body (under 100 words, plain text, conversational)

Format your response as:
SUBJECT: <subject line>
BODY: <email body>
"""


FOLLOWUP_PROMPTS = {
    "followup_1": """Write a 2-sentence follow-up email. Reference the previous email briefly.
Keep it casual and short. Don't re-pitch — just ask if they had a chance to look at it.
Company: {company_name}, Vertical: {vertical}

Format:
SUBJECT: Re: <very short>
BODY: <2 sentences>""",

    "followup_2": """Write a 3-sentence follow-up email with a DIFFERENT angle.
Share a specific result or case study relevant to their vertical ({vertical}).
Don't mention previous emails. Company: {company_name}

Format:
SUBJECT: <new short subject>
BODY: <3 sentences>""",

    "followup_3": """Write a 2-sentence breakup email. Let them know this is the last follow-up.
Keep it friendly, leave the door open. Company: {company_name}

Format:
SUBJECT: Closing the loop
BODY: <2 sentences>""",
}


def build_followup_prompt(step: str, prospect: dict) -> str:
    tmpl = FOLLOWUP_PROMPTS.get(step)
    if not tmpl:
        return ""
    return tmpl.format(
        company_name=prospect.get("company_name", ""),
        vertical=(prospect.get("vertical") or "").replace("_", " "),
    )


# --- Spintax ---

_SPINTAX_RE = re.compile(r"\{([^{}]+)\}")


def apply_spintax(text: str) -> str:
    """Replace {a|b|c} with a random choice. Handles nesting by iterating."""
    if not text:
        return text
    prev = None
    while prev != text:
        prev = text
        text = _SPINTAX_RE.sub(lambda m: random.choice(m.group(1).split("|")), text)
    return text


# Casual human-feeling signoffs with spintax
SIGNOFF_TEMPLATES = [
    "{Cheers|Best|Thanks},\n{Eric|E.}",
    "{Best|Thanks},\nEric",
    "Talk soon,\nEric",
]


def random_signoff() -> str:
    return apply_spintax(random.choice(SIGNOFF_TEMPLATES))


# --- Unsubscribe footer ---

UNSUBSCRIBE_TEXT = (
    "\n\n---\n"
    "If you'd rather not hear from us, reply \"unsubscribe\" and we'll remove you immediately."
)

UNSUBSCRIBE_HTML = (
    '<br><br><hr style="border:none;border-top:1px solid #ddd;margin:16px 0">'
    '<p style="color:#888;font-size:12px">'
    'If you\'d rather not hear from us, reply "unsubscribe" and we\'ll remove you immediately.'
    "</p>"
)


# --- Subject line validation (enforced pre-send) ---

_MAX_SUBJECT_WORDS = 8
_FORBIDDEN_SUBJECT_CHARS = set("!?")


def validate_subject(subject: str) -> tuple[bool, str]:
    s = (subject or "").strip().strip('"').strip("'")
    if not s:
        return False, "empty subject"
    words = s.split()
    if len(words) > _MAX_SUBJECT_WORDS + 2:  # allow "Re: " prefix
        return False, f"too long ({len(words)} words)"
    if s.isupper():
        return False, "all caps"
    if any(c in s for c in _FORBIDDEN_SUBJECT_CHARS):
        return False, "contains ! or ?"
    # strip emojis crudely (non-ascii letters that aren't part of normal text)
    non_ascii = [c for c in s if ord(c) > 127]
    if len(non_ascii) > 2:
        return False, "contains emojis/unicode"
    return True, s


def clean_subject(subject: str) -> str:
    """Best-effort cleanup."""
    s = (subject or "").strip().strip('"').strip("'")
    s = re.sub(r"[!?]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# --- Body validation ---

def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def clean_body(body: str) -> str:
    """Strip markdown bold, HTML tags (shouldn't be there), normalize whitespace."""
    b = (body or "").strip()
    b = re.sub(r"\*\*(.+?)\*\*", r"\1", b)
    b = re.sub(r"<[^>]+>", "", b)
    b = re.sub(r"\n{3,}", "\n\n", b)
    return b.strip()


def text_to_html(text: str) -> str:
    """Convert plain text body to a minimal HTML version."""
    import html
    escaped = html.escape(text or "")
    paragraphs = [p.strip() for p in escaped.split("\n\n") if p.strip()]
    body = "".join(
        f'<p style="margin:0 0 14px;font-family:-apple-system,Arial,sans-serif;font-size:14px;line-height:1.5;color:#222">{p.replace(chr(10), "<br>")}</p>'
        for p in paragraphs
    )
    return f'<div style="max-width:560px">{body}</div>'
