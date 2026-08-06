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

from src.search_keywords import get_search_keywords, is_qa_related as _is_qa_related

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

HYBRID_PATTERN = re.compile(
    r"\b(hybrid|part[\s-]?remote|flexible[\s-]?work(?:place| arrangement)?|"
    r"\d+[\s-]?days?\s+(?:in[\s-]?)?office|office[\s-]?hybrid)\b",
    re.IGNORECASE,
)
REMOTE_PATTERN = re.compile(
    r"\b(remote|work[\s-]?from[\s-]?home|wfh|fully[\s-]?remote|telecommute|"
    r"telecommuting|distributed(?:\s+team)?|work[\s-]?anywhere|100%[\s-]?remote|"
    r"location[\s-]?independent)\b",
    re.IGNORECASE,
)
OFFICE_PATTERN = re.compile(
    r"\b(on[\s-]?site|onsite|in[\s-]?office|office[\s-]?based|in[\s-]?person)\b",
    re.IGNORECASE,
)
REMOTE_LOCATION_HINTS = {
    "remote",
    "worldwide",
    "anywhere",
    "global",
    "work from home",
    "wfh",
}


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


def is_qa_related(title: str, description: str = "", config: dict | None = None) -> bool:
    """Match QA/testing roles using the shared keyword list."""
    return _is_qa_related(title, description, config)


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


def infer_work_mode(location: str = "", title: str = "", description: str = "") -> str:
    """Classify a role as Remote, Hybrid, or Office from location and posting text."""
    from src.models import WorkMode

    combined = f"{location} {title} {description}"
    location_lower = (location or "").strip().lower()

    if HYBRID_PATTERN.search(combined):
        return WorkMode.HYBRID.value
    if OFFICE_PATTERN.search(combined):
        return WorkMode.OFFICE.value
    if REMOTE_PATTERN.search(combined):
        return WorkMode.REMOTE.value

    if location_lower in REMOTE_LOCATION_HINTS or location_lower.startswith("remote"):
        return WorkMode.REMOTE.value
    if "hybrid" in location_lower:
        return WorkMode.HYBRID.value

    if location_lower and location_lower not in {"not specified", "see posting", "n/a", "unknown"}:
        return WorkMode.OFFICE.value

    return WorkMode.NOT_SPECIFIED.value


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
        work_mode: str | None = None,
        api_job_type: str | None = None,
        date_found: datetime | None = None,
    ) -> JobPosting | None:
        if not is_qa_related(role, jd_text, self.config):
            return None

        resolved_employment = employment_type or infer_employment_type(
            role, jd_text, api_job_type
        )
        if not matches_employment_filter(resolved_employment, role, jd_text, self.config):
            return None

        resolved_location = location.strip() or "Remote"
        resolved_work_mode = work_mode or infer_work_mode(resolved_location, role, jd_text)

        return JobPosting(
            company=company.strip(),
            role=role.strip(),
            jd_text=jd_text.strip(),
            location=resolved_location,
            experience_level=experience_level or infer_seniority(role, jd_text),
            employment_type=resolved_employment,
            work_mode=resolved_work_mode,
            source=source,
            contact_email=contact_email or extract_email(jd_text),
            posting_link=posting_link,
            date_found=date_found or datetime.utcnow(),
        )
