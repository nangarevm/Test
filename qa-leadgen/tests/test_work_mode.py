"""Tests for remote/hybrid/office work mode classification."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.aggregator.base import infer_work_mode
from src.export.excel_export import export_jobs_tracker, load_jobs_tracker
from src.models import JobPosting, JobStatus, WorkMode


def test_infer_work_mode_remote():
    assert infer_work_mode("Remote", "QA Engineer", "") == WorkMode.REMOTE.value
    assert infer_work_mode("Worldwide", "SDET", "work from home") == WorkMode.REMOTE.value
    assert infer_work_mode("Remote - US", "Tester", "") == WorkMode.REMOTE.value


def test_infer_work_mode_hybrid():
    assert infer_work_mode("London, UK", "QA Lead", "hybrid role, 2 days in office") == WorkMode.HYBRID.value
    assert infer_work_mode("Hybrid", "QA Analyst", "") == WorkMode.HYBRID.value


def test_infer_work_mode_office():
    assert infer_work_mode("San Francisco, CA", "QA Engineer", "") == WorkMode.OFFICE.value
    assert infer_work_mode("Berlin", "Tester", "on-site position") == WorkMode.OFFICE.value


def test_work_mode_export_and_load(tmp_path):
    jobs = [
        JobPosting(
            company="Acme",
            role="Remote QA",
            jd_text="fully remote team",
            location="Remote",
            work_mode=WorkMode.REMOTE.value,
            experience_level="Mid",
            employment_type="Contract",
            source="Test",
            posting_link="http://example.com",
            status=JobStatus.NEW,
        ),
        JobPosting(
            company="Beta",
            role="Hybrid QA",
            jd_text="hybrid schedule",
            location="Austin, TX",
            work_mode=WorkMode.HYBRID.value,
            experience_level="Senior",
            employment_type="Full-time",
            source="Test",
            posting_link="http://example.com/2",
            status=JobStatus.NEW,
        ),
    ]
    filepath = tmp_path / "tracker.xlsx"
    export_jobs_tracker(jobs, filepath)

    loaded = load_jobs_tracker(filepath)
    modes = {job.role: job.work_mode for job in loaded}
    assert modes["Remote QA"] == WorkMode.REMOTE.value
    assert modes["Hybrid QA"] == WorkMode.HYBRID.value


def test_work_mode_backfill_on_legacy_rows(tmp_path):
    import pandas as pd

    filepath = tmp_path / "legacy.xlsx"
    df = pd.DataFrame(
        [
            {
                "Company": "Legacy Co",
                "Role": "QA Engineer",
                "JD Summary": "hybrid work model",
                "Location": "Chicago, IL",
                "Experience Level": "Mid",
                "Employment Type": "Full-time",
                "Source": "Test",
                "Contact Email": "",
                "Posting Link": "http://example.com",
                "Date Found": "2026-08-06 10:00",
                "Status": "New",
            }
        ]
    )
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="All Jobs", index=False)

    loaded = load_jobs_tracker(filepath)
    assert len(loaded) == 1
    assert loaded[0].work_mode == WorkMode.HYBRID.value
