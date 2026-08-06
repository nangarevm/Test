"""Tests for daily Excel sheet export."""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.export.excel_export import (
    DAILY_SUMMARY_SHEET,
    MASTER_SHEET,
    OVERSEAS_DIRECTORY_SHEET,
    export_jobs_tracker,
    export_overseas_directory,
    load_jobs_tracker,
)
from src.models import JobPosting, JobStatus


def test_daily_sheet_export(tmp_path):
    jobs = [
        JobPosting(
            company="Acme",
            role="QA Engineer",
            jd_text="testing",
            location="Remote",
            experience_level="Mid",
            source="Test",
            posting_link="http://example.com",
            employment_type="Freelance",
            status=JobStatus.NEW,
        )
    ]
    daily = [
        JobPosting(
            company="Beta",
            role="SDET",
            jd_text="automation",
            location="UK",
            work_mode="Remote",
            experience_level="Senior",
            source="Test2",
            posting_link="http://example.com/2",
            employment_type="Contract",
            status=JobStatus.NEW,
        )
    ]
    filepath = tmp_path / "tracker.xlsx"
    sheet = export_jobs_tracker(jobs, filepath, daily_jobs=daily, export_day=date(2026, 8, 6))

    assert sheet == "2026-08-06"
    book = pd.read_excel(filepath, sheet_name=None)
    assert MASTER_SHEET in book
    assert "2026-08-06" in book
    assert DAILY_SUMMARY_SHEET in book
    assert len(book[MASTER_SHEET]) == 1
    assert len(book["2026-08-06"]) == 1
    assert book[DAILY_SUMMARY_SHEET].iloc[0]["Jobs Found Today"] == 1
    assert book[DAILY_SUMMARY_SHEET].iloc[0]["Remote"] == 1
    assert "Work Mode" in book[MASTER_SHEET].columns

    loaded = load_jobs_tracker(filepath)
    assert len(loaded) == 1
    assert loaded[0].company == "Acme"


def test_load_jobs_tracker_from_all_jobs_sheet(tmp_path):
    filepath = tmp_path / "tracker.xlsx"
    export_jobs_tracker([], filepath)
    loaded = load_jobs_tracker(filepath)
    assert loaded == []


def test_load_jobs_tracker_without_legacy_sheet(tmp_path):
    """Migrated workbooks use 'All Jobs' — no 'Job Requirements' sheet."""
    jobs = [
        JobPosting(
            company="Acme",
            role="QA Engineer",
            jd_text="testing",
            location="Remote",
            experience_level="Mid",
            source="Test",
            posting_link="http://example.com",
            employment_type="Freelance",
            status=JobStatus.NEW,
        )
    ]
    filepath = tmp_path / "tracker.xlsx"
    export_jobs_tracker(jobs, filepath)

    book = pd.read_excel(filepath, sheet_name=None)
    assert MASTER_SHEET in book
    assert "Job Requirements" not in book

    loaded = load_jobs_tracker(filepath)
    assert len(loaded) == 1
    assert loaded[0].company == "Acme"


def test_load_jobs_tracker_legacy_sheet(tmp_path):
    """Still read older trackers that only have the legacy sheet name."""
    filepath = tmp_path / "legacy_tracker.xlsx"
    df = pd.DataFrame(
        [
            {
                "Company": "Legacy Co",
                "Role": "SDET",
                "JD Summary": "automation",
                "Location": "Remote",
                "Experience Level": "Senior",
                "Employment Type": "Contract",
                "Source": "Test",
                "Contact Email": "",
                "Posting Link": "http://example.com",
                "Date Found": "2026-08-06 10:00",
                "Status": "New",
            }
        ]
    )
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Job Requirements", index=False)

    loaded = load_jobs_tracker(filepath)
    assert len(loaded) == 1
    assert loaded[0].company == "Legacy Co"


def test_overseas_directory_sheet(tmp_path):
    from src.aggregator.platforms_registry import load_platforms

    filepath = tmp_path / "tracker.xlsx"
    export_jobs_tracker([], filepath)
    export_overseas_directory(load_platforms(), filepath)
    book = pd.read_excel(filepath, sheet_name=None)
    assert OVERSEAS_DIRECTORY_SHEET in book
    assert len(book[OVERSEAS_DIRECTORY_SHEET]) > 100
