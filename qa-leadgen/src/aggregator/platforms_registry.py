"""Platform registry loader for 100+ remote job boards."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PLATFORMS_FILE = Path(__file__).parent.parent.parent / "platforms" / "platforms.yaml"
OVERSEAS_FILE = Path(__file__).parent.parent.parent / "platforms" / "overseas_software_jobs.yaml"


@dataclass
class Platform:
    id: str
    name: str
    category: str
    url: str
    country: str = ""
    adapter: str = "manual"
    feed_url: str = ""
    builtin_key: str = ""
    enabled_by_default: bool = False
    notes: str = ""
    json_mapping: dict[str, str] = field(default_factory=dict)
    requires_api_key: bool = False

    @property
    def is_fetchable(self) -> bool:
        if self.adapter == "manual":
            return False
        if self.adapter == "builtin":
            return bool(self.builtin_key)
        return bool(self.feed_url)


def load_platforms(path: Path | None = None) -> list[Platform]:
    if path:
        files = [path]
    else:
        files = [PLATFORMS_FILE, OVERSEAS_FILE]

    platforms: list[Platform] = []
    seen_ids: set[str] = set()
    for file_path in files:
        if not file_path.exists():
            continue
        with open(file_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        for item in raw.get("platforms", []):
            pid = item["id"]
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            platforms.append(
                Platform(
                    id=pid,
                    name=item["name"],
                    category=item.get("category", "other"),
                    url=item.get("url", ""),
                    country=item.get("country", ""),
                    adapter=item.get("adapter", "manual"),
                    feed_url=item.get("feed_url", ""),
                    builtin_key=item.get("builtin_key", ""),
                    enabled_by_default=item.get("enabled_by_default", False),
                    notes=item.get("notes", ""),
                    json_mapping=item.get("json_mapping", {}),
                    requires_api_key=item.get("requires_api_key", False),
                )
            )
    return platforms


def get_platform_by_id(platform_id: str, platforms: list[Platform] | None = None) -> Platform | None:
    items = platforms or load_platforms()
    for platform in items:
        if platform.id == platform_id:
            return platform
    return None


def resolve_enabled_platforms(config: dict) -> list[Platform]:
    all_platforms = load_platforms()
    registry_cfg = config.get("platform_registry", {})
    legacy_sources = config.get("sources", {})

    enabled_ids: set[str] = set()

    if registry_cfg.get("auto_enable_feeds"):
        for p in all_platforms:
            if p.is_fetchable and not p.requires_api_key:
                enabled_ids.add(p.id)

    for group in registry_cfg.get("groups", []):
        for p in all_platforms:
            if p.category == group and p.is_fetchable:
                enabled_ids.add(p.id)

    for platform_id in registry_cfg.get("include", []):
        enabled_ids.add(platform_id)

    for p in all_platforms:
        if p.enabled_by_default and p.is_fetchable:
            enabled_ids.add(p.id)

    # Legacy source toggles map to platform ids / builtin keys
    legacy_map = {
        "remoteok": "remoteok",
        "weworkremotely": "weworkremotely",
        "remotive": "remotive",
        "arbeitnow": "arbeitnow",
        "indeed": "indeed",
        "upwork": "upwork",
        "wellfound": "wellfound",
        "linkedin_jobs": "linkedin_jobs",
    }
    for legacy_key, platform_id in legacy_map.items():
        if legacy_key not in legacy_sources:
            continue
        if legacy_sources[legacy_key]:
            enabled_ids.add(platform_id)
        else:
            enabled_ids.discard(platform_id)

    for platform_id in registry_cfg.get("exclude", []):
        enabled_ids.discard(platform_id)

    # Respect requires_api_key unless credentials present
    import os

    api_gated = {
        "indeed": "INDEED_PUBLISHER_ID",
        "upwork": "UPWORK_ACCESS_TOKEN",
    }
    result = []
    for p in all_platforms:
        if p.id not in enabled_ids:
            continue
        env_key = api_gated.get(p.id)
        if env_key and not os.getenv(env_key):
            continue
        result.append(p)
    return result


def group_platforms(platforms: list[Platform]) -> dict[str, list[Platform]]:
    grouped: dict[str, list[Platform]] = {}
    for p in platforms:
        grouped.setdefault(p.category, []).append(p)
    return grouped


def category_label(category: str) -> str:
    labels = {
        "general_remote": "General Remote Job Boards",
        "freelance_gig": "Freelance / Gig Marketplaces",
        "tech_focused": "Tech-Focused",
        "startup_focused": "Startup-Focused",
        "region_specific": "Region-Specific",
        "overseas_software": "Overseas Software Job Boards",
        "writing": "Writing",
        "design": "Design",
        "customer_support": "Customer Support / VA",
        "marketing": "Marketing",
        "eor_global_hiring": "Employer-of-Record / Global Hiring",
        "large_aggregators": "Large General Aggregators",
        "other_niche": "Other Niche / Remote-Specific",
    }
    return labels.get(category, category.replace("_", " ").title())
