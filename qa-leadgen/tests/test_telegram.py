"""Tests for Telegram integration."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models import JobPosting, JobStatus
from src.notifications.telegram import TelegramNotifier


@pytest.fixture
def telegram_config():
    return {
        "telegram": {
            "enabled": True,
            "bot_token": "test-token",
            "chat_id": "12345",
            "include_company_directory": True,
        },
        "output": {
            "jobs_tracker": "job_requirements_tracker.xlsx",
            "company_directory": "company_directory.xlsx",
        },
    }


def test_is_configured(telegram_config):
    notifier = TelegramNotifier(telegram_config)
    assert notifier.is_configured is True

    telegram_config["telegram"]["enabled"] = False
    assert TelegramNotifier(telegram_config).is_configured is False


@patch("src.notifications.telegram.requests.post")
def test_send_message(mock_post, telegram_config):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"ok": True},
        raise_for_status=lambda: None,
    )
    notifier = TelegramNotifier(telegram_config)
    assert notifier.send_message("hello") is True
    mock_post.assert_called_once()


@patch("src.notifications.telegram.requests.post")
def test_send_document(mock_post, telegram_config, tmp_path):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"ok": True},
        raise_for_status=lambda: None,
    )
    test_file = tmp_path / "report.xlsx"
    test_file.write_bytes(b"fake excel")

    notifier = TelegramNotifier(telegram_config)
    assert notifier.send_document(test_file, caption="test") is True


def test_build_summary(telegram_config, tmp_path):
    from src.export.excel_export import export_jobs_tracker

    jobs_file = tmp_path / "job_requirements_tracker.xlsx"
    jobs = [
        JobPosting(
            company="Acme",
            role="QA Engineer",
            jd_text="testing",
            location="Remote",
            experience_level="Mid",
            employment_type="Freelance",
            source="Test",
            posting_link="http://example.com",
            status=JobStatus.NEW,
        )
    ]
    export_jobs_tracker(jobs, jobs_file)

    notifier = TelegramNotifier(telegram_config)
    summary = notifier.build_summary(jobs_file)
    assert "Jobs tracked: 1" in summary
    assert "Freelance/contract: 1" in summary
