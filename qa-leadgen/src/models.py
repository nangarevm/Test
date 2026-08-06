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


@dataclass
class JobPosting:
    company: str
    role: str
    jd_text: str
    location: str
    experience_level: str
    source: str
    posting_link: str
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
