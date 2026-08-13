"""Arbeitnow public job board API adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from src.aggregator.base import JobSource
from src.models import JobPosting, WorkMode


class ArbeitnowSource(JobSource):
    name = "Arbeitnow"
    API_URL = "https://www.arbeitnow.com/api/job-board-api"

    def fetch(self, keywords: Iterable[str]) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        resp = self._get(self.API_URL)
        data = resp.json()

        keyword_set = {k.lower() for k in keywords}
        for item in data.get("data", []):
            title = item.get("title", "")
            description = item.get("description", "") or ""
            tags = " ".join(item.get("tags", []) or [])
            searchable = f"{title} {description} {tags}".lower()
            if keyword_set and not any(k in searchable for k in keyword_set):
                continue

            location = "Remote" if item.get("remote") else (item.get("location", "") or "Not specified")
            work_mode = WorkMode.REMOTE.value if item.get("remote") else None
            api_job_type = None
            if "contract" in title.lower():
                api_job_type = "contract"
            elif item.get("remote"):
                api_job_type = "freelance" if "freelance" in searchable else None

            posting = self._make_posting(
                company=item.get("company_name", "Unknown"),
                role=title,
                jd_text=description,
                location=location,
                work_mode=work_mode,
                source=self.name,
                posting_link=item.get("url", ""),
                api_job_type=api_job_type,
                date_found=datetime.utcnow(),
            )
            if posting:
                jobs.append(posting)
        return jobs
