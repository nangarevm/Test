"""Tests for platform registry."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.aggregator.feed_adapters import JSONPlatformSource
from src.aggregator.platforms_registry import (
    Platform,
    category_label,
    load_platforms,
    resolve_enabled_platforms,
)


def test_load_all_platforms():
    platforms = load_platforms()
    assert len(platforms) >= 190
    ids = {p.id for p in platforms}
    assert len(ids) == len(platforms)
    assert "weworkremotely" in ids
    assert "jobicy" in ids
    assert "seek_au" in ids
    assert "bayt" in ids
    assert "vietnamworks" in ids
    assert "kariyer_tr" in ids


def test_country_coverage_summary():
    from src.aggregator.platforms_registry import country_coverage_summary

    summary = country_coverage_summary()
    assert summary["total_portals"] >= 190
    assert summary["countries_regions"] >= 55
    assert summary["global_portals"] >= 100
    assert summary["by_country"]["India"] >= 4
    assert summary["by_country"]["United Kingdom"] >= 4


def test_platform_categories():
    platforms = load_platforms()
    categories = {p.category for p in platforms}
    assert "general_remote" in categories
    assert "freelance_gig" in categories
    assert "tech_focused" in categories


def test_resolve_enabled_with_auto_feeds():
    config = {
        "sources": {},
        "platform_registry": {
            "auto_enable_feeds": True,
            "exclude": ["flexjobs"],
        },
    }
    enabled = resolve_enabled_platforms(config)
    enabled_ids = {p.id for p in enabled}
    assert "remoteok" in enabled_ids
    assert "himalayas" in enabled_ids
    assert "flexjobs" not in enabled_ids


def test_company_from_url():
    platform = Platform(id="test", name="Test", category="general_remote", url="")
    source = JSONPlatformSource({}, platform)
    assert source._company_from_url("https://landing.jobs/job/acme-corp/senior-qa") == "Acme Corp"


def test_category_label():
    assert "Remote" in category_label("general_remote")
