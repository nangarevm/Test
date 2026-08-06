"""Tests for remote QA company catalogs (USD, overseas, India)."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.company_sources import (
    catalog_summary,
    load_all_company_catalogs,
    load_company_catalog,
    resolve_company_sources,
)


def test_usd_catalog_has_500():
    companies = load_company_catalog()
    assert len(companies) == 500


def test_all_catalogs_total_2000_no_duplicates():
    companies = load_all_company_catalogs()
    assert len(companies) == 2000
    names = [c.name.lower() for c in companies]
    assert len(names) == len(set(names))
    ids = [c.id for c in companies]
    assert len(ids) == len(set(ids))


def test_catalog_group_counts():
    stats = catalog_summary()
    assert stats["by_catalog_group"]["usd_global"] == 500
    assert stats["by_catalog_group"]["overseas_global"] == 1000
    assert stats["by_catalog_group"]["india"] == 500
    assert stats["by_currency"]["USD"] == 500
    assert stats["by_currency"]["overseas"] == 1000
    assert stats["by_currency"]["INR"] == 500


def test_priority_companies_in_usd_catalog():
    companies = load_company_catalog()
    names = {c.name for c in companies}
    for expected in ("Toptal", "Synack", "Kodify Media Group", "InEight", "BrowserStack"):
        assert expected in names


def test_resolve_company_sources_filters():
    config = {
        "company_sources": {
            "enabled": True,
            "include_usd": True,
            "include_overseas": False,
            "include_india": False,
            "pays_usd_only": True,
        }
    }
    companies = resolve_company_sources(config)
    assert len(companies) == 500
    assert all(c.pays_usd for c in companies)

    india_only = resolve_company_sources({
        "company_sources": {
            "enabled": True,
            "include_usd": False,
            "include_overseas": False,
            "include_india": True,
        }
    })
    assert len(india_only) == 500
    assert all(c.catalog_group == "india" for c in india_only)
