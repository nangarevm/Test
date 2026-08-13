"""Tests for outreach contact selection safety gates."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.export.excel_export import export_company_directory
from src.models import CompanyContact
from src.outreach.tracker import OutreachManager


def _make_manager(tmp_path) -> OutreachManager:
    config = {"output": {"company_directory": "company_directory.xlsx"}, "email": {}}
    return OutreachManager(config, tmp_path)


def test_lookup_skips_unverified_contact(tmp_path):
    manager = _make_manager(tmp_path)
    export_company_directory(
        [CompanyContact(company="Acme Corp", general_contact_email="guess@acmecorp.com", verified=False)],
        tmp_path / "company_directory.xlsx",
    )

    assert manager._lookup_company_email("Acme Corp") is None


def test_lookup_returns_verified_contact(tmp_path):
    manager = _make_manager(tmp_path)
    export_company_directory(
        [CompanyContact(company="Acme Corp", general_contact_email="real@acmecorp.com", verified=True)],
        tmp_path / "company_directory.xlsx",
    )

    assert manager._lookup_company_email("Acme Corp") == "real@acmecorp.com"


def test_block_action_adds_to_suppression_list(tmp_path):
    manager = _make_manager(tmp_path)
    manager.suppression.add(email="jane@acme.com", company="Acme Corp", reason="manual block during review")

    assert manager.suppression.is_suppressed(email="jane@acme.com")
    assert manager.suppression.is_suppressed(company="Acme Corp")
