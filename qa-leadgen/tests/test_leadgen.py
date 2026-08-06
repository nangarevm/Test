"""Basic tests for QA lead-gen tool."""

import sys
from datetime import datetime
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.aggregator.base import extract_email, infer_seniority, is_qa_related
from src.aggregator.deduplicator import deduplicate_jobs
from src.models import JobPosting, JobStatus
from src.outreach.templates import render_email


def test_is_qa_related():
    assert is_qa_related("Senior QA Engineer", "manual testing")
    assert is_qa_related("SDET", "")
    assert is_qa_related("Software Tester", "automation experience required")
    assert is_qa_related("QA Consultant", "")
    assert is_qa_related("Playwright Engineer", "")
    assert is_qa_related("Manual Tester", "remote contract")
    assert not is_qa_related("Senior Java Backend Developer", "Spring Boot microservices")
    assert not is_qa_related("Avi Go", "quality assurance math ops golang")


def test_infer_employment_type():
    from src.aggregator.base import infer_employment_type, is_freelance_or_contract

    assert infer_employment_type("Freelance QA Tester", "") == "Freelance"
    assert infer_employment_type("QA Contractor", "6 month contract") == "Freelance"
    assert infer_employment_type("QA Engineer", "", api_job_type="contract") == "Contract"
    assert is_freelance_or_contract("Contract", "QA Lead", "")
    assert not is_freelance_or_contract("Full-time", "QA Lead", "full-time role")


def test_extract_email():
    assert extract_email("Contact us at hiring@acme.com for details") == "hiring@acme.com"
    assert extract_email("no email here") is None


def test_infer_seniority():
    assert infer_seniority("Junior QA Tester") == "Junior"
    assert infer_seniority("Senior SDET") == "Senior"
    assert infer_seniority("QA Analyst") == "Not specified"


def test_deduplicate_jobs():
    j1 = JobPosting(
        company="Acme", role="QA Engineer", jd_text="test", location="Remote",
        experience_level="Mid", employment_type="Freelance", source="A", posting_link="http://a.com",
    )
    j2 = JobPosting(
        company="Acme", role="QA Engineer", jd_text="longer description here",
        location="Remote", experience_level="Mid", employment_type="Contract", source="B",
        posting_link="http://b.com", contact_email="hr@acme.com",
    )
    result = deduplicate_jobs([j1, j2])
    assert len(result) == 1
    assert result[0].contact_email == "hr@acme.com"
    assert "longer" in result[0].jd_text


def test_render_email():
    subject, body = render_email(
        company="Acme Corp",
        role="QA Lead",
        jd_text="We need automation testing experience with Selenium.",
        user_config={"name": "Jane", "email": "jane@test.com", "phone": "555", "website": ""},
    )
    assert "Acme Corp" in subject
    assert "Jane" in body
    assert "unsubscribe" in body.lower()


def test_job_status_enum():
    assert JobStatus.NEW.value == "New"
