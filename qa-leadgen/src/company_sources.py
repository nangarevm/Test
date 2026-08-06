"""Remote QA company catalogs — USD, overseas currency, and India."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CATALOG_USD = Path(__file__).parent.parent / "config" / "remote_qa_companies.yaml"
CATALOG_OVERSEAS = Path(__file__).parent.parent / "config" / "remote_qa_companies_overseas.yaml"
CATALOG_INDIA = Path(__file__).parent.parent / "config" / "remote_qa_companies_india.yaml"
USER_PRIORITY_FILE = Path(__file__).parent.parent / "config" / "priority_company_sources.yaml"

CATALOG_FILES = {
    "usd_global": CATALOG_USD,
    "overseas_global": CATALOG_OVERSEAS,
    "india": CATALOG_INDIA,
}


@dataclass
class CompanySource:
    id: str
    name: str
    careers_url: str
    ats: str = "website"
    ats_slug: str = ""
    remote: bool = True
    pays_usd: bool = True
    currency: str = "USD"
    catalog_group: str = "usd_global"
    region: str = "global"
    notes: str = ""

    @property
    def is_ats_fetchable(self) -> bool:
        return self.ats in {"greenhouse", "lever", "recruitee"} and bool(self.ats_slug)

    @property
    def fetch_url(self) -> str:
        if self.ats == "greenhouse" and self.ats_slug:
            return f"https://boards-api.greenhouse.io/v1/boards/{self.ats_slug}/jobs"
        if self.ats == "lever" and self.ats_slug:
            return f"https://api.lever.co/v0/postings/{self.ats_slug}?mode=json"
        if self.ats == "recruitee" and self.ats_slug:
            return f"https://{self.ats_slug}.recruitee.com/api/offers/"
        return self.careers_url


def _parse_company(item: dict) -> CompanySource:
    return CompanySource(
        id=item["id"],
        name=item["name"],
        careers_url=item.get("careers_url", ""),
        ats=item.get("ats", "website"),
        ats_slug=item.get("ats_slug", ""),
        remote=bool(item.get("remote", True)),
        pays_usd=bool(item.get("pays_usd", True)),
        currency=item.get("currency", "USD" if item.get("pays_usd", True) else "overseas"),
        catalog_group=item.get("catalog_group", "usd_global"),
        region=item.get("region", "global"),
        notes=item.get("notes", ""),
    )


def _load_catalog_file(path: Path, default_group: str) -> list[CompanySource]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    companies = []
    for item in raw.get("companies", []):
        if "catalog_group" not in item:
            item = {**item, "catalog_group": default_group}
        companies.append(_parse_company(item))
    return companies


def load_company_catalog(path: Path | None = None) -> list[CompanySource]:
    """Load USD global catalog only (backward compatible)."""
    return _load_catalog_file(path or CATALOG_USD, "usd_global")


def load_all_company_catalogs() -> list[CompanySource]:
    """Load all catalogs (USD + overseas + India), deduplicated by id and name."""
    merged: dict[str, CompanySource] = {}
    name_seen: set[str] = set()

    for group, path in CATALOG_FILES.items():
        for company in _load_catalog_file(path, group):
            name_key = company.name.lower().strip()
            if company.id in merged or name_key in name_seen:
                continue
            merged[company.id] = company
            name_seen.add(name_key)

    for company in load_priority_companies():
        merged[company.id] = company
        name_seen.add(company.name.lower().strip())

    return sorted(merged.values(), key=lambda c: (c.catalog_group, c.name.lower()))


def load_priority_companies(path: Path | None = None) -> list[CompanySource]:
    path = path or USER_PRIORITY_FILE
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return [_parse_company(item) for item in raw.get("companies", [])]


def resolve_company_sources(config: dict) -> list[CompanySource]:
    """Return companies to scan, respecting config filters."""
    cfg = config.get("company_sources", {})
    if not cfg.get("enabled", True):
        return []

    if "catalogs" in cfg:
        include_groups = set(cfg["catalogs"])
    else:
        include_groups = set()
        if cfg.get("include_usd", True):
            include_groups.add("usd_global")
        if cfg.get("include_overseas", True):
            include_groups.add("overseas_global")
        if cfg.get("include_india", True):
            include_groups.add("india")
        if not include_groups:
            include_groups = {"usd_global", "overseas_global", "india"}

    companies = [c for c in load_all_company_catalogs() if c.catalog_group in include_groups]

    if cfg.get("remote_only", True):
        companies = [c for c in companies if c.remote]

    if cfg.get("pays_usd_only", False):
        companies = [c for c in companies if c.pays_usd]

    currency_filter = {c.lower() for c in cfg.get("currencies", []) or []}
    if currency_filter:
        companies = [c for c in companies if c.currency.lower() in currency_filter]

    region_filter = {r.lower() for r in cfg.get("regions", []) or []}
    if region_filter:
        companies = [
            c for c in companies
            if c.region.lower() in region_filter or c.region == "global"
        ]

    priority_ids = {c.id for c in load_priority_companies()}
    companies.sort(key=lambda c: (c.id not in priority_ids, c.catalog_group, c.name.lower()))
    return companies


def catalog_summary(companies: list[CompanySource] | None = None) -> dict:
    items = companies or load_all_company_catalogs()
    ats_fetchable = sum(1 for c in items if c.is_ats_fetchable)
    by_group: dict[str, int] = {}
    by_currency: dict[str, int] = {}
    for company in items:
        by_group[company.catalog_group] = by_group.get(company.catalog_group, 0) + 1
        by_currency[company.currency] = by_currency.get(company.currency, 0) + 1
    return {
        "total": len(items),
        "remote": sum(1 for c in items if c.remote),
        "pays_usd": sum(1 for c in items if c.pays_usd),
        "ats_fetchable": ats_fetchable,
        "website_only": len(items) - ats_fetchable,
        "by_catalog_group": by_group,
        "by_currency": by_currency,
        "by_ats": {
            ats: sum(1 for c in items if c.ats == ats)
            for ats in sorted({c.ats for c in items})
        },
    }
