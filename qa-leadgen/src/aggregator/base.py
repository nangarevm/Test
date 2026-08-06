"""Base classes and utilities for job source adapters."""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable

import requests

from src.models import JobPosting

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

QA_KEYWORDS = re.compile(
    r"\b(qa|quality assurance|software test|sdet|test engineer|automation engineer|"
    r"quality engineer|qe |testing)\b",
    re.IGNORECASE,
)

SENIORITY_PATTERNS = [
    (re.compile(r"\b(intern|entry[\s-]?level|junior)\b", re.I), "Junior"),
    (re.compile(r"\b(mid[\s-]?level|intermediate)\b", re.I), "Mid"),
    (re.compile(r"\b(senior|sr\.?|lead|principal|staff)\b", re.I), "Senior"),
    (re.compile(r"\b(manager|director|head of)\b", re.I), "Leadership"),
]


def extract_email(text: str) -> str | None:
    if not text:
        return None
    match = EMAIL_PATTERN.search(text)
    return match.group(0) if match else None


def infer_seniority(title: str, description: str = "") -> str:
    combined = f"{title} {description}"
    for pattern, level in SENIORITY_PATTERNS:
        if pattern.search(combined):
            return level
    return "Not specified"


def is_qa_related(title: str, description: str = "") -> bool:
    return bool(QA_KEYWORDS.search(f"{title} {description}"))


class JobSource(ABC):
    name: str = "base"

    def __init__(self, config: dict, session: requests.Session | None = None) -> None:
        self.config = config
        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent",
            config.get("enrichment", {}).get(
                "user_agent", "QA-LeadGen-Bot/1.0 (compliant job aggregator)"
            ),
        )

    @abstractmethod
    def fetch(self, keywords: Iterable[str]) -> list[JobPosting]:
        ...

    def _get(self, url: str, **kwargs) -> requests.Response:
        time.sleep(0.5)
        resp = self.session.get(url, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp

    def _make_posting(
        self,
        *,
        company: str,
        role: str,
        jd_text: str,
        location: str,
        source: str,
        posting_link: str,
        contact_email: str | None = None,
        experience_level: str | None = None,
        date_found: datetime | None = None,
    ) -> JobPosting | None:
        if not is_qa_related(role, jd_text):
            return None
        return JobPosting(
            company=company.strip(),
            role=role.strip(),
            jd_text=jd_text.strip(),
            location=location.strip() or "Remote",
            experience_level=experience_level or infer_seniority(role, jd_text),
            source=source,
            contact_email=contact_email or extract_email(jd_text),
            posting_link=posting_link,
            date_found=date_found or datetime.utcnow(),
        )
