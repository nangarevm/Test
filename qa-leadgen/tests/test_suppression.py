"""Tests for the outreach opt-out suppression list."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.outreach.suppression import SuppressionList


def test_add_and_is_suppressed_by_email(tmp_path):
    sup = SuppressionList(tmp_path / "suppression_list.json")
    assert not sup.is_suppressed(email="jane@acme.com")

    sup.add(email="Jane@Acme.com", reason="unsubscribe")
    assert sup.is_suppressed(email="jane@acme.com")
    assert sup.is_suppressed(email="JANE@ACME.COM")


def test_add_and_is_suppressed_by_company():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        sup = SuppressionList(Path(d) / "suppression_list.json")
        sup.add(company="Acme Inc")
        assert sup.is_suppressed(company="acme inc")
        assert not sup.is_suppressed(company="Other Inc")


def test_suppression_persists_across_instances(tmp_path):
    state_file = tmp_path / "suppression_list.json"
    SuppressionList(state_file).add(email="a@b.com", company="Acme")

    reloaded = SuppressionList(state_file)
    assert reloaded.is_suppressed(email="a@b.com")
    assert len(reloaded.all()) == 1


def test_remove(tmp_path):
    sup = SuppressionList(tmp_path / "suppression_list.json")
    sup.add(email="a@b.com")
    assert sup.remove(email="a@b.com") is True
    assert not sup.is_suppressed(email="a@b.com")
    assert sup.remove(email="a@b.com") is False


def test_matches_by_either_email_or_company(tmp_path):
    sup = SuppressionList(tmp_path / "suppression_list.json")
    sup.add(company="Acme Inc")
    # A new job at the same company, different contact email, is still suppressed.
    assert sup.is_suppressed(email="new-contact@acme.com", company="Acme Inc")
