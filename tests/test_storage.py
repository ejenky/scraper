from pathlib import Path

from core.models import ContactPerson, Prospect, SocialLinks, Source, Vertical
from core.storage import append_csv, load_csv, save_csv


def test_round_trip_csv(tmp_path: Path):
    p = Prospect(
        company_name="Stake",
        domain="stake.com",
        website="https://stake.com",
        vertical=Vertical.CASINO,
        source=Source.GOOGLE_SEARCH,
        primary_email="partners@stake.com",
        all_emails=["partners@stake.com", "media@stake.com"],
        contacts=[ContactPerson(name="Ed Craven", title="CEO")],
        socials=SocialLinks(twitter="https://twitter.com/Stake"),
        has_affiliate_program=True,
        score=85,
    )
    f = tmp_path / "out.csv"
    save_csv(f, [p])
    loaded = load_csv(f)
    assert len(loaded) == 1
    q = loaded[0]
    assert q.company_name == "Stake"
    assert q.primary_email == "partners@stake.com"
    assert "media@stake.com" in q.all_emails
    assert q.contacts[0].name == "Ed Craven"
    assert q.socials.twitter.startswith("https://twitter.com/")
    assert q.has_affiliate_program
    assert q.score == 85


def test_append_csv(tmp_path: Path):
    f = tmp_path / "a.csv"
    p1 = Prospect(company_name="A", domain="a.com", vertical=Vertical.CASINO, source=Source.GOOGLE_SEARCH)
    p2 = Prospect(company_name="B", domain="b.com", vertical=Vertical.CRYPTO, source=Source.GOOGLE_SEARCH)
    append_csv(f, [p1])
    append_csv(f, [p2])
    loaded = load_csv(f)
    assert {p.company_name for p in loaded} == {"A", "B"}
