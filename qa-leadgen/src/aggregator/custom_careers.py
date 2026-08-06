"""Custom company career page scraper for user-specified URLs."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.aggregator.base import JobSource, extract_email, is_qa_related
from src.models import JobPosting


class CustomCareerPageSource(JobSource):
    """
    Scrapes user-specified company career pages for QA job postings.
    Only accesses pages the user explicitly configures.
    """

    name = "Custom Career Page"

    def fetch(self, keywords: Iterable[str]) -> list[JobPosting]:
        urls = self.config.get("sources", {}).get("custom_career_pages", [])
        jobs: list[JobPosting] = []
        for url in urls:
            try:
                jobs.extend(self._scrape_career_page(url, keywords))
            except Exception:
                continue
        return jobs

    def _scrape_career_page(self, base_url: str, keywords: Iterable[str]) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        resp = self._get(base_url)
        soup = BeautifulSoup(resp.text, "lxml")
        company = self._extract_company_name(soup, base_url)
        keyword_set = {k.lower() for k in keywords}

        job_links = self._find_job_links(soup, base_url)
        for link_info in job_links:
            title = link_info["title"]
            href = link_info["href"]
            searchable = title.lower()
            if keyword_set and not any(k in searchable for k in keyword_set):
                if not is_qa_related(title):
                    continue

            description = ""
            contact_email = None
            try:
                detail_resp = self._get(href)
                detail_soup = BeautifulSoup(detail_resp.text, "lxml")
                desc_el = (
                    detail_soup.select_one(".job-description")
                    or detail_soup.select_one("[class*='description']")
                    or detail_soup.select_one("article")
                    or detail_soup.select_one("main")
                )
                if desc_el:
                    description = desc_el.get_text(separator=" ", strip=True)
                    contact_email = extract_email(description)
            except Exception:
                description = title

            posting = self._make_posting(
                company=company,
                role=title,
                jd_text=description or title,
                location="See posting",
                source=f"{self.name} ({urlparse(base_url).netloc})",
                posting_link=href,
                contact_email=contact_email,
                date_found=datetime.utcnow(),
            )
            if posting:
                jobs.append(posting)
        return jobs

    def _find_job_links(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        links: list[dict] = []
        seen: set[str] = set()

        selectors = [
            "a[href*='job']",
            "a[href*='career']",
            "a[href*='position']",
            ".job-listing a",
            ".opening a",
            "[data-job-id] a",
        ]
        for selector in selectors:
            for anchor in soup.select(selector):
                href = anchor.get("href", "")
                title = anchor.get_text(strip=True)
                if not href or not title or len(title) < 5:
                    continue
                full_url = urljoin(base_url, href)
                if full_url in seen:
                    continue
                seen.add(full_url)
                links.append({"title": title, "href": full_url})
        return links

    @staticmethod
    def _extract_company_name(soup: BeautifulSoup, url: str) -> str:
        og_site = soup.select_one("meta[property='og:site_name']")
        if og_site and og_site.get("content"):
            return og_site["content"]
        title = soup.find("title")
        if title:
            text = title.get_text(strip=True)
            for sep in ["|", "-", "–"]:
                if sep in text:
                    return text.split(sep)[0].strip()
            return text
        return urlparse(url).netloc
