"""Company contact enrichment from public business sources."""

from __future__ import annotations

import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from rich.console import Console

from src.aggregator.base import EMAIL_PATTERN, extract_email
from src.models import CompanyContact, JobPosting

console = Console()

COMMON_CONTACT_PATHS = [
    "/contact",
    "/contact-us",
    "/about/contact",
    "/company/contact",
    "/about-us",
    "/about",
]

HR_EMAIL_PATTERNS = [
    "careers@{domain}",
    "jobs@{domain}",
    "hr@{domain}",
    "recruiting@{domain}",
    "talent@{domain}",
    "hiring@{domain}",
]


class CompanyEnricher:
    """Looks up publicly listed business contact info — no LinkedIn profile scraping."""

    def __init__(self, config: dict) -> None:
        self.config = config
        self.delay = config.get("enrichment", {}).get("request_delay_seconds", 2)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = config.get("enrichment", {}).get(
            "user_agent", "QA-LeadGen-Bot/1.0"
        )

    def enrich_companies(self, jobs: list[JobPosting]) -> list[CompanyContact]:
        companies_without_contact = {
            j.company: j for j in jobs if not j.contact_email
        }
        results: list[CompanyContact] = []

        for company_name, job in companies_without_contact.items():
            console.print(f"[cyan]Enriching: {company_name}[/cyan]")
            contact = self._enrich_single(company_name, job)
            results.append(contact)
            time.sleep(self.delay)

        return results

    def _enrich_single(self, company_name: str, job: JobPosting) -> CompanyContact:
        contact = CompanyContact(company=company_name, location=job.location)

        website = self._guess_website(company_name, job)
        if website:
            contact.website = website
            email, source, confirmed = self._find_contact_on_site(website, company_name)
            if email:
                contact.general_contact_email = email
                contact.enrichment_source = source
                # Only trust the email if the site actually mentions this company —
                # `website` may be a guessed domain that resolves to an unrelated site.
                contact.verified = confirmed

        if not contact.general_contact_email and contact.website:
            domain = urlparse(contact.website).netloc.replace("www.", "")
            contact.general_contact_email = self._suggest_hr_email(domain)
            contact.enrichment_source = "inferred HR email pattern (unverified — confirm before contacting)"
            contact.verified = False

        return contact

    def _guess_website(self, company_name: str, job: JobPosting) -> str:
        if job.posting_link:
            parsed = urlparse(job.posting_link)
            if parsed.netloc and "linkedin" not in parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"

        slug = re.sub(r"[^a-z0-9]", "", company_name.lower())
        if slug:
            return f"https://www.{slug}.com"
        return ""

    def _find_contact_on_site(self, website: str, company_name: str) -> tuple[str, str, bool]:
        """Returns (email, source, company_confirmed).

        company_confirmed is True only if a fetched page actually mentions the
        company by name — `website` may be an unverified guessed domain, so we
        can't otherwise tell whether we scraped the right company's site.
        """
        base = website.rstrip("/")
        pages_to_check = [base] + [urljoin(base, path) for path in COMMON_CONTACT_PATHS]
        name_tokens = [
            tok for tok in re.sub(r"[^a-z0-9 ]", "", company_name.lower()).split() if len(tok) > 2
        ]
        confirmed = False

        for page_url in pages_to_check:
            try:
                resp = self.session.get(page_url, timeout=15, allow_redirects=True)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                page_text = soup.get_text(separator=" ")

                if not confirmed and name_tokens:
                    title_text = soup.title.get_text() if soup.title else ""
                    haystack = f"{title_text} {page_text}".lower()
                    confirmed = any(tok in haystack for tok in name_tokens)

                # mailto links are the most reliable public contact source
                for anchor in soup.select("a[href^='mailto:']"):
                    href = anchor.get("href", "")
                    email = href.replace("mailto:", "").split("?")[0].strip()
                    if EMAIL_PATTERN.match(email):
                        return email, f"mailto link on {page_url}", confirmed

                email = extract_email(page_text)
                if email and not self._is_generic_spam_trap(email):
                    return email, f"public page {page_url}", confirmed

            except Exception:
                continue
            time.sleep(0.5)

        return "", "", confirmed

    @staticmethod
    def _suggest_hr_email(domain: str) -> str:
        if domain:
            return HR_EMAIL_PATTERNS[0].format(domain=domain)
        return ""

    @staticmethod
    def _is_generic_spam_trap(email: str) -> bool:
        blocked = {"noreply", "no-reply", "donotreply", "mailer-daemon", "postmaster"}
        local = email.split("@")[0].lower()
        return local in blocked

    @staticmethod
    def _extract_meta(soup: BeautifulSoup, field: str) -> str:
        for meta in soup.select("meta"):
            content = meta.get("content", "")
            name = (meta.get("name", "") + meta.get("property", "")).lower()
            if field.lower() in name:
                return content
        return ""
