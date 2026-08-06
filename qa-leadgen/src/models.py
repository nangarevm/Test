"""Data models for job postings, companies, and outreach."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    NEW = "New"
    CONTACTED = "Contacted"
    RESPONDED = "Responded"
    CLOSED = "Closed"


class EmailStatus(str, Enum):
    DRAFT = "Draft"
    SENT = "Sent"
    OPENED = "Opened"
    REPLIED = "Replied"
    BOUNCED = "Bounced"


class WorkMode(str, Enum):
    REMOTE = "Remote"
    HYBRID = "Hybrid"
    OFFICE = "Office"
    NOT_SPECIFIED = "Not specified"


@dataclass
class JobPosting:
    company: str
    role: str
    jd_text: str
    location: str
    experience_level: str
    source: str
    posting_link: str
    employment_type: str = "Not specified"
    work_mode: str = WorkMode.NOT_SPECIFIED.value
    job_region: str = ""
    date_found: datetime = field(default_factory=datetime.utcnow)
    contact_email: Optional[str] = None
    status: JobStatus = JobStatus.NEW
    jd_summary: str = ""
    dedup_key: str = ""

    def __post_init__(self) -> None:
        if not self.jd_summary and self.jd_text:
            self.jd_summary = self._summarize(self.jd_text)
        if not self.dedup_key:
            self.dedup_key = f"{self.company.lower().strip()}|{self.role.lower().strip()}"
        if not self.job_region:
            from src.regions import infer_job_region

            self.job_region = infer_job_region(self.location, self.jd_text, self.role)

    @staticmethod
    def _summarize(text: str, max_len: int = 300) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= max_len:
            return cleaned
        return cleaned[: max_len - 3] + "..."


@dataclass
class CompanyContact:
    company: str
    website: str = ""
    industry: str = ""
    size: str = ""
    general_contact_email: str = ""
    location: str = ""
    enrichment_source: str = ""


@dataclass
class OutreachEmail:
    job_dedup_key: str
    to_email: str
    subject: str
    body: str
    status: EmailStatus = EmailStatus.DRAFT
    sent_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
