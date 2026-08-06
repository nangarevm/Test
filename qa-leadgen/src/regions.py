"""Job market regions: USA, Europe, Australia, and UAE."""

from __future__ import annotations

import re

from src.models import JobPosting

REGION_LABELS = {
    "usa": "USA",
    "europe": "Europe",
    "australia": "Australia",
    "uae": "UAE",
}

EUROPE_COUNTRIES = {
    "united kingdom",
    "uk",
    "ireland",
    "germany",
    "france",
    "netherlands",
    "switzerland",
    "spain",
    "italy",
    "portugal",
    "poland",
    "czech republic",
    "sweden",
    "belgium",
    "austria",
    "norway",
    "denmark",
    "finland",
    "hungary",
    "romania",
    "slovakia",
    "croatia",
    "greece",
    "turkey",
    "ukraine",
    "luxembourg",
    "europe",
    "eu",
}

COUNTRY_TO_REGION = {
    "United States": "usa",
    "United Kingdom": "europe",
    "Ireland": "europe",
    "Germany": "europe",
    "France": "europe",
    "Netherlands": "europe",
    "Switzerland": "europe",
    "Spain": "europe",
    "Italy": "europe",
    "Portugal": "europe",
    "Poland": "europe",
    "Czech Republic": "europe",
    "Sweden": "europe",
    "Belgium": "europe",
    "Austria": "europe",
    "Norway": "europe",
    "Denmark": "europe",
    "Finland": "europe",
    "Hungary": "europe",
    "Romania": "europe",
    "Slovakia": "europe",
    "Croatia": "europe",
    "Greece": "europe",
    "Turkey": "europe",
    "Ukraine": "europe",
    "Luxembourg": "europe",
    "Australia": "australia",
    "New Zealand": "australia",
    "United Arab Emirates": "uae",
}

US_STATE_PATTERN = re.compile(
    r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|"
    r"MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|"
    r"WV|WI|WY|DC)\b"
)
REMOTE_PATTERN = re.compile(
    r"\b(remote|worldwide|anywhere|global|work from home|wfh|distributed)\b",
    re.IGNORECASE,
)
UAE_PATTERN = re.compile(
    r"\b(uae|dubai|abu dhabi|sharjah|ajman|ras al khaimah|fujairah|"
    r"united arab emirates|gulf)\b",
    re.IGNORECASE,
)
AUSTRALIA_PATTERN = re.compile(
    r"\b(australia|australian|sydney|melbourne|brisbane|perth|adelaide|"
    r"canberra|hobart|darwin|new zealand|auckland|wellington)\b",
    re.IGNORECASE,
)
USA_PATTERN = re.compile(
    r"\b(united states|usa|u\.s\.a?|america|us-?only|remote[\s-]?us)\b",
    re.IGNORECASE,
)


def normalize_regions(regions: list[str] | None) -> list[str]:
    if not regions:
        return []
    normalized = []
    for region in regions:
        key = region.strip().lower()
        if key in REGION_LABELS and key not in normalized:
            normalized.append(key)
    return normalized


def platform_regions(country: str = "") -> list[str]:
    """Return which search regions a portal primarily serves."""
    if not country or country == "Global":
        return list(REGION_LABELS.keys())
    mapped = COUNTRY_TO_REGION.get(country)
    return [mapped] if mapped else []


def infer_job_region(location: str = "", description: str = "", title: str = "") -> str:
    """Classify a job into USA, Europe, Australia, UAE, Global, or Other."""
    text = f"{location} {title} {description}".lower()
    location_text = (location or "").strip()

    if UAE_PATTERN.search(text):
        return REGION_LABELS["uae"]
    if AUSTRALIA_PATTERN.search(text):
        return REGION_LABELS["australia"]
    if (
        USA_PATTERN.search(text)
        or US_STATE_PATTERN.search(location_text.upper())
        or re.search(r",\s*(usa|us)\b", text)
    ):
        return REGION_LABELS["usa"]
    if any(country in text for country in EUROPE_COUNTRIES):
        return REGION_LABELS["europe"]
    if REMOTE_PATTERN.search(text):
        return "Global"
    if location_text and location_text.lower() not in {"not specified", "see posting", "n/a"}:
        return "Other"
    return "Other"


def job_matches_regions(job: JobPosting, regions: list[str]) -> bool:
    """Return True if the job matches any configured region (remote/global always included)."""
    selected = normalize_regions(regions)
    if not selected:
        return True

    region = job.job_region or infer_job_region(job.location, job.jd_text, job.role)
    if region == "Global":
        return True
    if region == "Other":
        return False

    region_key = next((key for key, label in REGION_LABELS.items() if label == region), "")
    return region_key in selected


def filter_jobs_by_regions(jobs: list[JobPosting], regions: list[str] | None) -> list[JobPosting]:
    selected = normalize_regions(regions)
    if not selected:
        return jobs
    return [job for job in jobs if job_matches_regions(job, selected)]


def region_portal_summary(platforms: list) -> dict[str, dict[str, int]]:
    """Count portals per target region."""
    summary: dict[str, dict[str, int]] = {}
    for key, label in REGION_LABELS.items():
        matched = []
        for platform in platforms:
            country = getattr(platform, "country", "") or "Global"
            if key in platform_regions(country):
                matched.append(platform)
        summary[label] = {
            "total": len(matched),
            "fetchable": sum(1 for p in matched if p.is_fetchable),
        }
    return summary
