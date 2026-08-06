"""Upwork API adapter (requires OAuth credentials)."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Iterable

from src.aggregator.base import JobSource
from src.models import JobPosting


class UpworkSource(JobSource):
    """
    Upwork GraphQL API for job search.
    Requires UPWORK_ACCESS_TOKEN with jobs:read scope.
    See: https://www.upwork.com/developer/documentation/graphql/api/docs/index.html
    """

    name = "Upwork"
    API_URL = "https://api.upwork.com/graphql"

    QUERY = """
    query SearchJobs($query: String!) {
      marketplaceJobPostingsSearch(
        marketPlaceJobFilter: { searchExpression_eq: $query }
        sortAttributes: [{ field: RECENCY }]
      ) {
        edges {
          node {
            id
            title
            description
            createdDateTime
            client {
              companyName
            }
            job {
              contractTerms {
                contractType
              }
            }
          }
        }
      }
    }
    """

    def fetch(self, keywords: Iterable[str]) -> list[JobPosting]:
        token = os.getenv("UPWORK_ACCESS_TOKEN", "")
        if not token:
            return []

        jobs: list[JobPosting] = []
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        for keyword in keywords:
            try:
                resp = self.session.post(
                    self.API_URL,
                    json={"query": self.QUERY, "variables": {"query": keyword}},
                    headers=headers,
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                continue

            edges = (
                data.get("data", {})
                .get("marketplaceJobPostingsSearch", {})
                .get("edges", [])
            )
            for edge in edges:
                node = edge.get("node", {})
                title = node.get("title", "")
                description = node.get("description", "") or ""
                company = (node.get("client") or {}).get("companyName", "Unknown")
                job_id = node.get("id", "")

                date_found = datetime.utcnow()
                created = node.get("createdDateTime")
                if created:
                    try:
                        date_found = datetime.fromisoformat(created.replace("Z", "+00:00")).replace(
                            tzinfo=None
                        )
                    except ValueError:
                        pass

                posting = self._make_posting(
                    company=company,
                    role=title,
                    jd_text=description,
                    location="Remote",
                    source=self.name,
                    posting_link=f"https://www.upwork.com/jobs/{job_id}",
                    date_found=date_found,
                )
                if posting:
                    jobs.append(posting)
        return jobs
