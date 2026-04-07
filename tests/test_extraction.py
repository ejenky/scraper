from enrichment.affiliate_detector import has_affiliate_program
from enrichment.contact_finder import extract_contacts
from enrichment.email_finder import extract_emails, is_valid_email, pick_primary
from enrichment.social_finder import extract_socials


def test_extract_emails_basic():
    html = """
    <a href="mailto:hello@example.io">hello</a>
    partnerships@stake.com and marketing@stake.com
    <img src="logo.png">
    noreply@spam.com
    """
    emails = extract_emails(html)
    assert "hello@example.io" in emails
    assert "partnerships@stake.com" in emails
    assert "marketing@stake.com" in emails
    assert not any("noreply" in e for e in emails)
    assert not any(".png" in e for e in emails)


def test_pick_primary_prefers_partnerships():
    emails = ["info@acme.com", "partnerships@acme.com", "hello@acme.com"]
    assert pick_primary(emails) == "partnerships@acme.com"


def test_is_valid_email():
    assert is_valid_email("a@b.co")
    assert not is_valid_email("bad")
    assert not is_valid_email("foo@example.com")  # blacklisted


def test_extract_socials():
    html = """
    <a href="https://twitter.com/rocketbrands">tw</a>
    <a href="https://www.linkedin.com/company/stake">li</a>
    <a href="https://t.me/casinogroup">tg</a>
    """
    s = extract_socials(html)
    assert "twitter.com/rocketbrands" in s.twitter
    assert "linkedin.com/company/stake" in s.linkedin
    assert "t.me/casinogroup" in s.telegram


def test_affiliate_detector():
    assert has_affiliate_program("Join our Affiliate Program today and earn commissions")
    assert not has_affiliate_program("Just a regular about page")


def test_extract_contacts():
    text = "John Smith - Head of Marketing at Acme. Jane Doe - CEO of something."
    contacts = extract_contacts(text)
    names = [c.name for c in contacts]
    assert "John Smith" in names
    assert "Jane Doe" in names
