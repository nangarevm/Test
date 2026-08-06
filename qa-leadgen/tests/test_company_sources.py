"""Tests for 500-company remote QA catalog."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.company_sources import catalog_summary, load_company_catalog, resolve_company_sources


def test_company_catalog_has_500():
    companies = load_company_catalog()
    assert len(companies) == 500
    summary = catalog_summary(companies)
    assert summary["total"] == 500
    assert summary["pays_usd"] == 500
    assert summary["remote"] == 500
    assert summary["ats_fetchable"] >= 50


def test_priority_companies_in_catalog():
    companies = load_company_catalog()
    names = {c.name for c in companies}
    for expected in ("Toptal", "Synack", "Kodify Media Group", "InEight", "BrowserStack"):
        assert expected in names


def test_resolve_company_sources():
    config = {
        "company_sources": {
            "enabled": True,
            "remote_only": True,
            "pays_usd_only": True,
            "regions": ["usa"],
        }
    }
    companies = resolve_company_sources(config)
    assert len(companies) > 0
    assert all(c.pays_usd for c in companies)
