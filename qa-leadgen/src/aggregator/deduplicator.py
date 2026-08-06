"""Deduplicate job postings across sources."""

from __future__ import annotations

from src.models import JobPosting, WorkMode


def deduplicate_jobs(jobs: list[JobPosting]) -> list[JobPosting]:
    seen: dict[str, JobPosting] = {}
    for job in jobs:
        key = job.dedup_key
        if key not in seen:
            seen[key] = job
            continue
        existing = seen[key]
        if not existing.contact_email and job.contact_email:
            existing.contact_email = job.contact_email
        if len(job.jd_text) > len(existing.jd_text):
            existing.jd_text = job.jd_text
            existing.jd_summary = job.jd_summary
        if job.posting_link and not existing.posting_link:
            existing.posting_link = job.posting_link
        if (
            existing.work_mode == WorkMode.NOT_SPECIFIED.value
            and job.work_mode != WorkMode.NOT_SPECIFIED.value
        ):
            existing.work_mode = job.work_mode
    return list(seen.values())
