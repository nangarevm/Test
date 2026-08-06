"""We Work Remotely RSS feed adapter."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable
from xml.etree import ElementTree

from src.aggregator.base import JobSource, extract_email
from src.models import JobPosting

QA_CATEGORIES = [
    "https://weworkremotely.com/categories/remote-qa-jobs.rss",
]


class WeWorkRemotelySource(JobSource):
    name = "We Work Remotely"

    def fetch(self, keywords: Iterable[str]) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        for feed_url in QA_CATEGORIES:
            try:
                resp = self._get(feed_url)
                jobs.extend(self._parse_rss(resp.text, keywords))
            except Exception:
                continue
        return jobs

    def _parse_rss(self, xml_text: str, keywords: Iterable[str]) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        root = ElementTree.fromstring(xml_text)
        keyword_set = {k.lower() for k in keywords}

        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            description = item.findtext("description", "") or ""
            pub_date = item.findtext("pubDate", "")

            company, role = self._parse_title(title)
            if not self._is_qa_title(title, description):
                continue
            searchable = f"{title} {description}".lower()
            if keyword_set and not any(k in searchable for k in keyword_set):
                continue

            date_found = self._parse_date(pub_date)
            posting = self._make_posting(
                company=company,
                role=role,
                jd_text=self._strip_html(description),
                location="Remote",
                source=self.name,
                posting_link=link,
                contact_email=extract_email(description),
                date_found=date_found,
            )
            if posting:
                jobs.append(posting)
        return jobs

    @staticmethod
    def _parse_title(title: str) -> tuple[str, str]:
        if ":" in title:
            company, role = title.split(":", 1)
            return company.strip(), role.strip()
        return "Unknown", title.strip()

    @staticmethod
    def _strip_html(text: str) -> str:
        return re.sub(r"<[^>]+>", " ", text)

    @staticmethod
    def _parse_date(pub_date: str) -> datetime:
        try:
            from email.utils import parsedate_to_datetime

            return parsedate_to_datetime(pub_date).replace(tzinfo=None)
        except Exception:
            return datetime.utcnow()

    @staticmethod
    def _is_qa_title(title: str, description: str) -> bool:
        from src.aggregator.base import is_qa_related

        return is_qa_related(title, description)
