"""RemoteOK public API adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from src.aggregator.base import JobSource
from src.models import JobPosting


class RemoteOKSource(JobSource):
    name = "RemoteOK"
    API_URL = "https://remoteok.com/api"

    def fetch(self, keywords: Iterable[str]) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        try:
            resp = self._get(self.API_URL, headers={"Accept": "application/json"})
            data = resp.json()
        except Exception:
            return jobs

        keyword_set = {k.lower() for k in keywords}
        for item in data:
            if not isinstance(item, dict) or "position" not in item:
                continue
            title = item.get("position", "")
            tags = " ".join(item.get("tags", []) or [])
            description = item.get("description", "") or ""
            searchable = f"{title} {tags} {description}".lower()
            if keyword_set and not any(k in searchable for k in keyword_set):
                continue
            if not any(t in tags.lower() for t in ("qa", "testing", "sdet", "quality")):
                continue

            epoch = item.get("epoch")
            date_found = (
                datetime.utcfromtimestamp(epoch) if epoch else datetime.utcnow()
            )
            posting = self._make_posting(
                company=item.get("company", "Unknown"),
                role=title,
                jd_text=description,
                location=item.get("location", "Remote") or "Remote",
                source=self.name,
                posting_link=item.get("url", f"https://remoteok.com/remote-jobs/{item.get('id', '')}"),
                date_found=date_found,
            )
            if posting:
                jobs.append(posting)
        return jobs
