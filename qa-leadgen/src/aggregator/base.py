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

QA_TITLE_PATTERN = re.compile(
    r"\b(qa\b|q\.a\.|quality assurance|software test(?:er|ing)?|sdet|test engineer|"
    r"automation engineer|quality engineer|qe\b|qa engineer|manual test(?:er|ing)?|"
    r"automation test(?:er|ing)?|uat\b|quality analyst)\b",
    re.IGNORECASE,
)

QA_DESCRIPTION_PATTERN = re.compile(
    r"\b(qa\b|quality assurance|software test|sdet|test engineer|automation engineer|"
    r"quality engineer|test automation|manual testing|qa team)\b",
    re.IGNORECASE,
)

FREELANCE_PATTERN = re.compile(
    r"\b(freelance|freelancer|contract(?:or)?|consulting|1099|gig work|project[\s-]based)\b",
    re.IGNORECASE,
)

PART_TIME_PATTERN = re.compile(r"\b(part[\s-]?time)\b", re.IGNORECASE)
FULL_TIME_PATTERN = re.compile(r"\b(full[\s-]?time)\b", re.IGNORECASE)

API_JOB_TYPE_MAP = {
    "freelance": "Freelance",
    "contract": "Contract",
    "full_time": "Full-time",
    "part_time": "Part-time",
    "temporary": "Contract",
    "internship": "Internship",
}

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
    """Require a strong QA signal in the title, or QA terms in both title and description."""
    if QA_TITLE_PATTERN.search(title):
        return True
    title_has_test_hint = bool(re.search(r"\b(test|quality|qa)\b", title, re.IGNORECASE))
    return title_has_test_hint and bool(QA_DESCRIPTION_PATTERN.search(description))


def infer_employment_type(
    title: str, description: str = "", api_job_type: str | None = None
) -> str:
    if api_job_type:
        normalized = API_JOB_TYPE_MAP.get(api_job_type.lower().strip())
        if normalized:
            return normalized

    combined = f"{title} {description}"
    if FREELANCE_PATTERN.search(combined):
        return "Freelance"
    if PART_TIME_PATTERN.search(combined):
        return "Part-time"
    if FULL_TIME_PATTERN.search(combined):
        return "Full-time"
    return "Not specified"


def is_freelance_or_contract(employment_type: str, title: str, description: str = "") -> bool:
    if employment_type in {"Freelance", "Contract", "Part-time"}:
        return True
    combined = f"{title} {description}"
    return bool(FREELANCE_PATTERN.search(combined) or PART_TIME_PATTERN.search(combined))


def matches_employment_filter(employment_type: str, title: str, description: str, config: dict) -> bool:
    search = config.get("search", {})
    if not search.get("only_freelance", False):
        return True

    allowed = {t.lower().replace("-", "_").replace(" ", "_") for t in search.get("employment_types", [])}
    normalized = employment_type.lower().replace("-", "_").replace(" ", "_")
    if normalized in allowed:
        return True

    combined = f"{title} {description}".lower()
    if "freelance" in allowed and FREELANCE_PATTERN.search(combined):
        return True
    if "contract" in allowed and re.search(r"\bcontract", combined):
        return True
    if "part_time" in allowed and PART_TIME_PATTERN.search(combined):
        return True
    return False


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
        employment_type: str | None = None,
        api_job_type: str | None = None,
        date_found: datetime | None = None,
    ) -> JobPosting | None:
        if not is_qa_related(role, jd_text):
            return None

        resolved_employment = employment_type or infer_employment_type(
            role, jd_text, api_job_type
        )
        if not matches_employment_filter(resolved_employment, role, jd_text, self.config):
            return None

        return JobPosting(
            company=company.strip(),
            role=role.strip(),
            jd_text=jd_text.strip(),
            location=location.strip() or "Remote",
            experience_level=experience_level or infer_seniority(role, jd_text),
            employment_type=resolved_employment,
            source=source,
            contact_email=contact_email or extract_email(jd_text),
            posting_link=posting_link,
            date_found=date_found or datetime.utcnow(),
        )
