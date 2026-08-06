"""Tests for automation daemon."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.automation.daemon import (
    daemon_status,
    is_process_running,
    pid_file_path,
    read_pid,
    remove_pid,
    write_pid,
)


def test_pid_file_roundtrip(tmp_path):
    config = {"automation": {"pid_file": "qa-leadgen.pid"}}
    pid_path = pid_file_path(config, tmp_path)
    write_pid(pid_path, 12345)
    assert read_pid(pid_path) == 12345
    remove_pid(pid_path)
    assert read_pid(pid_path) is None


def test_daemon_status_not_running(tmp_path):
    config = {"automation": {}}
    status = daemon_status(config, tmp_path)
    assert status["running"] is False
    assert status["pid"] is None


@patch("src.automation.daemon.is_process_running", return_value=True)
def test_daemon_status_running(mock_running, tmp_path):
    config = {"automation": {"pid_file": "qa-leadgen.pid"}}
    pid_path = pid_file_path(config, tmp_path)
    write_pid(pid_path, 999)
    status = daemon_status(config, tmp_path)
    assert status["running"] is True
    assert status["pid"] == 999


def test_is_process_running_current_pid():
    import os
    assert is_process_running(os.getpid()) is True
    assert is_process_running(999999999) is False
