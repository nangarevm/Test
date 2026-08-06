"""Remotive public API adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from src.aggregator.base import JobSource
from src.models import JobPosting


class RemotiveSource(JobSource):
    name = "Remotive"
    API_URL = "https://remotive.com/api/remote-jobs"

    def fetch(self, keywords: Iterable[str]) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        try:
            resp = self._get(self.API_URL, params={"category": "qa"})
            data = resp.json()
        except Exception:
            return jobs

        keyword_set = {k.lower() for k in keywords}
        for item in data.get("jobs", []):
            title = item.get("title", "")
            description = item.get("description", "") or ""
            tags = " ".join(item.get("tags", []) or [])
            searchable = f"{title} {description} {tags}".lower()
            if keyword_set and not any(k in searchable for k in keyword_set):
                continue

            pub_date = item.get("publication_date")
            date_found = datetime.utcnow()
            if pub_date:
                try:
                    date_found = datetime.fromisoformat(pub_date.replace("Z", "+00:00")).replace(
                        tzinfo=None
                    )
                except ValueError:
                    pass

            posting = self._make_posting(
                company=item.get("company_name", "Unknown"),
                role=title,
                jd_text=description,
                location=item.get("candidate_required_location", "Remote") or "Remote",
                source=self.name,
                posting_link=item.get("url", ""),
                date_found=date_found,
            )
            if posting:
                jobs.append(posting)
        return jobs
