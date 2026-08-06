"""Indeed Publisher API adapter (requires official API key)."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Iterable

from src.aggregator.base import JobSource, extract_email
from src.models import JobPosting


class IndeedSource(JobSource):
    name = "Indeed"
    API_URL = "https://api.indeed.com/ads/apisearch"

    def fetch(self, keywords: Iterable[str]) -> list[JobPosting]:
        publisher_id = os.getenv("INDEED_PUBLISHER_ID", "")
        if not publisher_id:
            return []

        jobs: list[JobPosting] = []
        for keyword in keywords:
            try:
                resp = self._get(
                    self.API_URL,
                    params={
                        "publisher": publisher_id,
                        "q": keyword,
                        "l": "",
                        "format": "json",
                        "v": "2",
                        "limit": 25,
                    },
                )
                data = resp.json()
            except Exception:
                continue

            for item in data.get("results", []):
                title = item.get("jobtitle", "")
                company = item.get("company", "Unknown")
                snippet = item.get("snippet", "")
                location = item.get("formattedLocation", "Not specified")
                url = item.get("url", "")
                date_str = item.get("date", "")

                date_found = datetime.utcnow()
                if date_str:
                    try:
                        date_found = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
                    except ValueError:
                        pass

                posting = self._make_posting(
                    company=company,
                    role=title,
                    jd_text=snippet,
                    location=location,
                    source=self.name,
                    posting_link=url,
                    contact_email=extract_email(snippet),
                    date_found=date_found,
                )
                if posting:
                    jobs.append(posting)
        return jobs
