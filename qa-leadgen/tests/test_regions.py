"""Tests for USA/Europe/Australia/UAE region handling."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models import JobPosting, JobStatus
from src.regions import (
    filter_jobs_by_regions,
    infer_job_region,
    platform_regions,
    region_portal_summary,
)
from src.aggregator.platforms_registry import load_platforms


def test_infer_job_region_targets():
    assert infer_job_region("Austin, TX", "", "QA Engineer") == "USA"
    assert infer_job_region("London, UK", "", "SDET") == "Europe"
    assert infer_job_region("Sydney, Australia", "", "Tester") == "Australia"
    assert infer_job_region("Dubai, UAE", "", "QA Lead") == "UAE"
    assert infer_job_region("Remote", "", "QA Engineer") == "Global"


def test_filter_jobs_by_regions():
    jobs = [
        JobPosting(
            company="US Co",
            role="QA",
            jd_text="",
            location="New York, NY",
            experience_level="Mid",
            source="Test",
            posting_link="http://example.com",
            job_region="USA",
            status=JobStatus.NEW,
        ),
        JobPosting(
            company="IN Co",
            role="QA",
            jd_text="",
            location="Bangalore, India",
            experience_level="Mid",
            source="Test",
            posting_link="http://example.com/2",
            job_region="Other",
            status=JobStatus.NEW,
        ),
    ]
    filtered = filter_jobs_by_regions(jobs, ["usa"])
    assert len(filtered) == 1
    assert filtered[0].company == "US Co"


def test_platform_regions():
    assert platform_regions("United States") == ["usa"]
    assert platform_regions("Germany") == ["europe"]
    assert platform_regions("Australia") == ["australia"]
    assert platform_regions("United Arab Emirates") == ["uae"]
    assert set(platform_regions("Global")) == {"usa", "europe", "australia", "uae"}


def test_region_portal_summary():
    summary = region_portal_summary(load_platforms())
    assert summary["USA"]["total"] >= 8
    assert summary["Europe"]["total"] >= 35
    assert summary["Australia"]["total"] >= 5
    assert summary["UAE"]["total"] >= 4
