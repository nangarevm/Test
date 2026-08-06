"""LinkedIn public job search (postings only, no profile scraping)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from src.aggregator.base import JobSource
from src.models import JobPosting


class LinkedInJobsSource(JobSource):
    """
    Fetches publicly visible LinkedIn job postings via their job search page.
    Does NOT scrape profiles or personal contact information.
    """

    name = "LinkedIn Jobs"
    BASE_URL = "https://www.linkedin.com/jobs/search"

    def fetch(self, keywords: Iterable[str]) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        for keyword in keywords:
            try:
                url = f"{self.BASE_URL}?keywords={quote_plus(keyword)}&f_WT=2"
                resp = self._get(url)
                jobs.extend(self._parse_search_results(resp.text, keyword))
            except Exception:
                continue
        return jobs

    def _parse_search_results(self, html: str, keyword: str) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        soup = BeautifulSoup(html, "lxml")

        for card in soup.select(".base-card") or soup.select(".job-search-card"):
            title_el = card.select_one(".base-search-card__title") or card.select_one("h3")
            company_el = card.select_one(".base-search-card__subtitle") or card.select_one("h4")
            location_el = card.select_one(".job-search-card__location")
            link_el = card.select_one("a[href*='/jobs/view/']") or card.select_one("a")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            company = company_el.get_text(strip=True) if company_el else "Unknown"
            location = location_el.get_text(strip=True) if location_el else "Not specified"
            link = link_el.get("href", "") if link_el else ""
            if link and "?" in link:
                link = link.split("?")[0]

            posting = self._make_posting(
                company=company,
                role=title,
                jd_text=f"QA position found via LinkedIn Jobs search for '{keyword}'.",
                location=location,
                source=self.name,
                posting_link=link,
                date_found=datetime.utcnow(),
            )
            if posting:
                jobs.append(posting)
        return jobs
