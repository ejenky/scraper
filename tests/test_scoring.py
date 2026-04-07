from core.models import ContactPerson, Prospect, SocialLinks, Source, Vertical
from pipeline import score_prospect


def test_score_low():
    p = Prospect(company_name="X", vertical=Vertical.CASINO, source=Source.GOOGLE_SEARCH)
    assert score_prospect(p) == 0


def test_score_high():
    p = Prospect(
        company_name="Stake",
        vertical=Vertical.CASINO,
        source=Source.GOOGLE_SEARCH,
        primary_email="partnerships@stake.com",
        all_emails=["partnerships@stake.com", "media@stake.com"],
        has_affiliate_program=True,
        contacts=[ContactPerson(name="X", title="Head of Marketing")],
        socials=SocialLinks(
            linkedin="https://linkedin.com/company/stake",
            twitter="https://twitter.com/Stake",
            instagram="https://instagram.com/stake",
        ),
    )
    assert score_prospect(p) >= 70
