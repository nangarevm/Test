"""Remote QA company catalog — USD-paying employers worldwide."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CATALOG_FILE = Path(__file__).parent.parent / "config" / "remote_qa_companies.yaml"
USER_PRIORITY_FILE = Path(__file__).parent.parent / "config" / "priority_company_sources.yaml"


@dataclass
class CompanySource:
    id: str
    name: str
    careers_url: str
    ats: str = "website"
    ats_slug: str = ""
    remote: bool = True
    pays_usd: bool = True
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
        region=item.get("region", "global"),
        notes=item.get("notes", ""),
    )


def load_company_catalog(path: Path | None = None) -> list[CompanySource]:
    path = path or CATALOG_FILE
    if not path.exists():
        return []

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    companies: list[CompanySource] = []
    seen: set[str] = set()
    for item in raw.get("companies", []):
        company = _parse_company(item)
        if company.id in seen:
            continue
        seen.add(company.id)
        companies.append(company)
    return companies


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

    companies = load_company_catalog()
    priority = {c.id: c for c in load_priority_companies()}
    merged: dict[str, CompanySource] = {c.id: c for c in companies}
    merged.update(priority)

    result = list(merged.values())
    if cfg.get("remote_only", True):
        result = [c for c in result if c.remote]
    if cfg.get("pays_usd_only", True):
        result = [c for c in result if c.pays_usd]

    region_filter = {r.lower() for r in cfg.get("regions", []) or []}
    if region_filter:
        result = [c for c in result if c.region.lower() in region_filter or c.region == "global"]

    priority_ids = {c.id for c in load_priority_companies()}
    result.sort(key=lambda c: (c.id not in priority_ids, c.name.lower()))
    return result


def catalog_summary(companies: list[CompanySource] | None = None) -> dict:
    items = companies or load_company_catalog()
    ats_fetchable = sum(1 for c in items if c.is_ats_fetchable)
    return {
        "total": len(items),
        "remote": sum(1 for c in items if c.remote),
        "pays_usd": sum(1 for c in items if c.pays_usd),
        "ats_fetchable": ats_fetchable,
        "website_only": len(items) - ats_fetchable,
        "by_ats": {
            ats: sum(1 for c in items if c.ats == ats)
            for ats in sorted({c.ats for c in items})
        },
    }
