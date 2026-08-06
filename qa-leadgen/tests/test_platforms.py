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


def test_load_all_100_platforms():
    platforms = load_platforms()
    assert len(platforms) == 100
    ids = {p.id for p in platforms}
    assert len(ids) == 100
    assert "weworkremotely" in ids
    assert "upwork" in ids
    assert "himalayas" in ids
    assert "nodesk_europe" in ids


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
