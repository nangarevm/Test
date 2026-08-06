"""Tests for interactive Telegram bot commands."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.notifications.telegram_bot import ScanningState, TelegramBotController


@pytest.fixture
def bot_config(tmp_path):
    return {
        "telegram": {
            "enabled": True,
            "bot_token": "test-token",
            "chat_id": "12345",
            "interval_hours": 12,
        },
        "output": {
            "jobs_tracker": "job_requirements_tracker.xlsx",
            "company_directory": "company_directory.xlsx",
        },
    }


def test_scanning_state_start_stop(tmp_path):
    state = ScanningState(tmp_path / "state.json", interval_hours=12)
    assert state.scanning_enabled is False
    state.start_scanning()
    assert state.scanning_enabled is True
    assert state.data["next_scan_at"] is not None
    state.stop_scanning()
    assert state.scanning_enabled is False


def test_handle_start_stop_commands(bot_config, tmp_path):
    controller = TelegramBotController(
        bot_config,
        tmp_path,
        fetch_fn=MagicMock(),
        send_fn=MagicMock(return_value=True),
    )

    with patch.object(controller, "reply") as mock_reply:
        controller.handle_command("12345", "/start")
        assert controller.state.scanning_enabled is True
        mock_reply.assert_called()

        controller.handle_command("12345", "/stop")
        assert controller.state.scanning_enabled is False


def test_handle_scan_command(bot_config, tmp_path):
    fetch = MagicMock()
    send = MagicMock(return_value=True)
    controller = TelegramBotController(bot_config, tmp_path, fetch_fn=fetch, send_fn=send)

    with patch.object(controller, "reply"):
        controller.handle_command("12345", "/scan")
        fetch.assert_called_once()
        send.assert_not_called()


def test_handle_scanreport_command(bot_config, tmp_path):
    fetch = MagicMock()
    send = MagicMock(return_value=True)
    controller = TelegramBotController(bot_config, tmp_path, fetch_fn=fetch, send_fn=send)

    with patch.object(controller, "reply"):
        controller.handle_command("12345", "/scanreport")
        fetch.assert_called_once()
        send.assert_called_once()


def test_unauthorized_chat_ignored(bot_config, tmp_path):
    controller = TelegramBotController(
        bot_config,
        tmp_path,
        fetch_fn=MagicMock(),
        send_fn=MagicMock(return_value=True),
    )
    fetch = controller.fetch_fn
    with patch.object(controller, "reply") as mock_reply:
        controller.handle_command("99999", "/scan")
        mock_reply.assert_not_called()
        fetch.assert_not_called()
