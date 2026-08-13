"""Custom company career page and ATS board fetcher."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from rich.console import Console

from src.aggregator.base import JobSource, extract_email, is_qa_related
from src.company_sources import CompanySource, resolve_company_sources
from src.models import JobPosting

console = Console()


class CustomCareerPageSource(JobSource):
    """Fetch QA roles from configured company career pages and ATS boards."""

    name = "Company Careers"

    def fetch(self, keywords: Iterable[str]) -> list[JobPosting]:
        cfg = self.config.get("company_sources", {})
        max_ats = int(cfg.get("max_ats_fetch_per_run", 75))
        companies = resolve_company_sources(self.config)
        extra_urls = self.config.get("sources", {}).get("custom_career_pages", [])

        jobs: list[JobPosting] = []
        ats_fetched = 0
        for company in companies:
            if company.is_ats_fetchable:
                if ats_fetched >= max_ats:
                    continue
                try:
                    batch = self._fetch_ats_company(company, keywords)
                    jobs.extend(batch)
                except Exception as exc:
                    console.print(f"  [yellow]{self.name}: {company.name} ({company.ats}) failed: {exc}[/yellow]")
                ats_fetched += 1
                continue
            if cfg.get("fetch_website_pages", False):
                try:
                    jobs.extend(self._scrape_career_page(company.careers_url, keywords, company.name))
                except Exception as exc:
                    console.print(f"  [yellow]{self.name}: {company.name} careers page failed: {exc}[/yellow]")
                    continue

        for url in extra_urls:
            try:
                jobs.extend(self._scrape_career_page(url, keywords))
            except Exception as exc:
                console.print(f"  [yellow]{self.name}: {url} failed: {exc}[/yellow]")
                continue
        return jobs

    def _fetch_ats_company(self, company: CompanySource, keywords: Iterable[str]) -> list[JobPosting]:
        if company.ats == "greenhouse":
            return self._fetch_greenhouse(company, keywords)
        if company.ats == "lever":
            return self._fetch_lever(company, keywords)
        if company.ats == "recruitee":
            return self._fetch_recruitee(company, keywords)
        return []

    def _fetch_greenhouse(self, company: CompanySource, keywords: Iterable[str]) -> list[JobPosting]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{company.ats_slug}/jobs?content=true"
        resp = self.session.get(url, timeout=30)
        if resp.status_code != 200:
            return []
        jobs: list[JobPosting] = []
        for item in resp.json().get("jobs", []):
            title = item.get("title", "")
            description = item.get("content", "") or ""
            location = (item.get("location") or {}).get("name", "Remote")
            posting = self._make_posting(
                company=company.name,
                role=title,
                jd_text=description,
                location=location,
                source=f"{self.name} ({company.ats})",
                posting_link=item.get("absolute_url", company.careers_url),
                contact_email=extract_email(description),
                date_found=datetime.utcnow(),
            )
            if posting:
                jobs.append(posting)
        return jobs

    def _fetch_lever(self, company: CompanySource, keywords: Iterable[str]) -> list[JobPosting]:
        url = f"https://api.lever.co/v0/postings/{company.ats_slug}?mode=json"
        resp = self.session.get(url, timeout=30)
        if resp.status_code != 200:
            return []
        jobs: list[JobPosting] = []
        for item in resp.json():
            title = item.get("text", "")
            description = item.get("descriptionPlain", "") or ""
            location = item.get("categories", {}).get("location", "Remote")
            posting = self._make_posting(
                company=company.name,
                role=title,
                jd_text=description,
                location=location,
                source=f"{self.name} ({company.ats})",
                posting_link=item.get("hostedUrl", company.careers_url),
                contact_email=extract_email(description),
                date_found=datetime.utcnow(),
            )
            if posting:
                jobs.append(posting)
        return jobs

    def _fetch_recruitee(self, company: CompanySource, keywords: Iterable[str]) -> list[JobPosting]:
        url = f"https://{company.ats_slug}.recruitee.com/api/offers/"
        resp = self.session.get(url, timeout=30)
        if resp.status_code != 200:
            return []
        jobs: list[JobPosting] = []
        for item in resp.json().get("offers", []):
            title = item.get("title", "")
            description = item.get("description", "") or ""
            location = item.get("location", "Remote") or "Remote"
            posting = self._make_posting(
                company=company.name,
                role=title,
                jd_text=description,
                location=location,
                source=f"{self.name} ({company.ats})",
                posting_link=item.get("careers_url", company.careers_url),
                contact_email=extract_email(description),
                date_found=datetime.utcnow(),
            )
            if posting:
                jobs.append(posting)
        return jobs

    def _scrape_career_page(
        self,
        base_url: str,
        keywords: Iterable[str],
        company_name: str | None = None,
    ) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        resp = self._get(base_url)
        soup = BeautifulSoup(resp.text, "lxml")
        company = company_name or self._extract_company_name(soup, base_url)

        for link_info in self._find_job_links(soup, base_url):
            title = link_info["title"]
            href = link_info["href"]
            if not is_qa_related(title):
                continue

            description = title
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
                pass

            posting = self._make_posting(
                company=company,
                role=title,
                jd_text=description,
                location="Remote",
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
