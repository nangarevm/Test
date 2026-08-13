"""Wellfound (AngelList) public job listings adapter."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Iterable

from src.aggregator.base import JobSource
from src.models import JobPosting


class WellfoundSource(JobSource):
    """
    Fetches public job listings from Wellfound's job board.
    Uses publicly accessible listing pages (no profile scraping).
    """

    name = "Wellfound"
    SEARCH_URL = "https://wellfound.com/job_listings/remote/quality-assurance"

    def fetch(self, keywords: Iterable[str]) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        resp = self._get(self.SEARCH_URL)
        html = resp.text

        # Wellfound embeds job data in JSON-LD or script tags on listing pages
        for match in re.finditer(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
        ):
            try:
                ld = json.loads(match.group(1))
                items = ld if isinstance(ld, list) else [ld]
                for item in items:
                    if item.get("@type") != "JobPosting":
                        continue
                    posting = self._from_json_ld(item, keywords)
                    if posting:
                        jobs.append(posting)
            except (json.JSONDecodeError, KeyError):
                continue

        # Fallback: parse basic job cards from HTML structure
        if not jobs:
            jobs = self._parse_html_cards(html, keywords)
        return jobs

    def _from_json_ld(self, item: dict, keywords: Iterable[str]) -> JobPosting | None:
        title = item.get("title", "")
        description = item.get("description", "") or ""
        company = (item.get("hiringOrganization") or {}).get("name", "Unknown")
        location_obj = item.get("jobLocation", {})
        if isinstance(location_obj, list):
            location_obj = location_obj[0] if location_obj else {}
        address = location_obj.get("address", {})
        location = address.get("addressLocality", "Remote") if isinstance(address, dict) else "Remote"
        url = item.get("url", "")

        keyword_set = {k.lower() for k in keywords}
        searchable = f"{title} {description}".lower()
        if keyword_set and not any(k in searchable for k in keyword_set):
            return None

        return self._make_posting(
            company=company,
            role=title,
            jd_text=description,
            location=location,
            source=self.name,
            posting_link=url,
        )

    def _parse_html_cards(self, html: str, keywords: Iterable[str]) -> list[JobPosting]:
        from bs4 import BeautifulSoup

        jobs: list[JobPosting] = []
        soup = BeautifulSoup(html, "lxml")
        for card in soup.select("[data-test='JobListing']") or soup.select(".job-listing"):
            title_el = card.select_one("a[href*='/jobs/']") or card.select_one("h2")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = f"https://wellfound.com{link}"
            company_el = card.select_one("[data-test='startup-name']") or card.select_one(".company")
            company = company_el.get_text(strip=True) if company_el else "Unknown"
            desc_el = card.select_one(".job-description") or card.select_one("p")
            description = desc_el.get_text(strip=True) if desc_el else title

            posting = self._make_posting(
                company=company,
                role=title,
                jd_text=description,
                location="Remote",
                source=self.name,
                posting_link=link,
            )
            if posting:
                jobs.append(posting)
        return jobs
