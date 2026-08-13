"""Tests for company contact enrichment domain verification."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.enrichment.company_enricher import CompanyEnricher
from src.models import JobPosting


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class FakeSession:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.headers = {}

    def get(self, url, timeout=None, allow_redirects=None):
        if url in self.pages:
            return FakeResponse(200, self.pages[url])
        return FakeResponse(404, "")


def _make_enricher(pages: dict[str, str]) -> CompanyEnricher:
    enricher = CompanyEnricher({})
    enricher.session = FakeSession(pages)
    return enricher


def test_confirms_company_when_name_appears_on_site():
    pages = {
        "https://www.acmecorp.com": "<html><title>Acme Corp - Home</title><body>Welcome</body></html>",
        "https://www.acmecorp.com/contact": (
            "<html><body><a href='mailto:hello@acmecorp.com'>Email us</a></body></html>"
        ),
    }
    enricher = _make_enricher(pages)
    email, source, confirmed = enricher._find_contact_on_site("https://www.acmecorp.com", "Acme Corp")

    assert email == "hello@acmecorp.com"
    assert confirmed is True


def test_does_not_confirm_unrelated_site():
    # Guessed domain resolves to a real but unrelated company's site.
    pages = {
        "https://www.acmecorp.com": (
            "<html><title>Totally Different Co</title>"
            "<body>Contact us at info@totallydifferent.com</body></html>"
        ),
    }
    enricher = _make_enricher(pages)
    email, source, confirmed = enricher._find_contact_on_site("https://www.acmecorp.com", "Acme Corp")

    assert email == "info@totallydifferent.com"
    assert confirmed is False


def test_enrich_single_marks_unconfirmed_email_unverified():
    pages = {
        "https://www.acmecorp.com": (
            "<html><title>Totally Different Co</title>"
            "<body>Contact us at info@totallydifferent.com</body></html>"
        ),
    }
    enricher = _make_enricher(pages)
    job = JobPosting(
        company="Acme Corp",
        role="QA Engineer",
        jd_text="Test QA role",
        location="Remote",
        experience_level="Mid",
        source="Test",
        posting_link="",
    )
    contact = enricher._enrich_single("Acme Corp", job)

    assert contact.general_contact_email == "info@totallydifferent.com"
    assert contact.verified is False


def test_enrich_single_marks_confirmed_email_verified():
    pages = {
        "https://www.acmecorp.com": "<html><title>Acme Corp - Home</title><body>Welcome</body></html>",
        "https://www.acmecorp.com/contact": (
            "<html><body><a href='mailto:hello@acmecorp.com'>Email us</a></body></html>"
        ),
    }
    enricher = _make_enricher(pages)
    job = JobPosting(
        company="Acme Corp",
        role="QA Engineer",
        jd_text="Test QA role",
        location="Remote",
        experience_level="Mid",
        source="Test",
        posting_link="",
    )
    contact = enricher._enrich_single("Acme Corp", job)

    assert contact.general_contact_email == "hello@acmecorp.com"
    assert contact.verified is True


def test_inferred_hr_email_fallback_is_never_verified():
    # No mailto/page email found anywhere -> falls back to a guessed careers@ address.
    pages = {"https://www.acmecorp.com": "<html><title>Acme Corp</title><body>Hi</body></html>"}
    enricher = _make_enricher(pages)
    job = JobPosting(
        company="Acme Corp",
        role="QA Engineer",
        jd_text="Test QA role",
        location="Remote",
        experience_level="Mid",
        source="Test",
        posting_link="",
    )
    contact = enricher._enrich_single("Acme Corp", job)

    assert contact.general_contact_email == "careers@acmecorp.com"
    assert contact.verified is False
