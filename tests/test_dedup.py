from core.deduplication import Deduplicator, normalize_company_name, normalize_domain
from core.models import Prospect, Source, Vertical


def test_normalize_domain():
    assert normalize_domain("https://www.Example.com/path?x=1") == "example.com"
    assert normalize_domain("http://foo.io") == "foo.io"
    assert normalize_domain("www.bar.co.uk/y") == "bar.co.uk"
    assert normalize_domain("") == ""


def test_normalize_company_name():
    assert normalize_company_name("Acme Inc.") == "acme"
    assert normalize_company_name("Stake  Casino LLC") == "stake casino"
    assert normalize_company_name("FooBar® Corp") == "foobar"


def test_dedup_merge():
    d = Deduplicator()
    p1 = Prospect(
        company_name="Acme",
        domain="acme.com",
        website="https://acme.com",
        vertical=Vertical.CASINO,
        source=Source.GOOGLE_SEARCH,
        primary_email="",
    )
    p2 = Prospect(
        company_name="Acme Inc.",
        domain="acme.com",
        website="https://acme.com",
        vertical=Vertical.CASINO,
        source=Source.GOOGLE_PLAY,
        primary_email="partners@acme.com",
        all_emails=["partners@acme.com"],
    )
    d.add(p1)
    merged = d.add(p2)
    assert merged.primary_email == "partners@acme.com"
    assert "partners@acme.com" in merged.all_emails
    assert len(d.all()) == 1
