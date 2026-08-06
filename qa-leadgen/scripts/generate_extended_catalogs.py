#!/usr/bin/env python3
"""Generate overseas (1000) and India (500) QA company catalogs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
EXISTING_NAMES = ROOT / "scripts" / "existing_company_names.txt"
OVERSEAS_NAMES = ROOT / "scripts" / "overseas_qa_company_names.txt"
INDIA_NAMES = ROOT / "scripts" / "india_qa_company_names.txt"
OVERSEAS_OUT = ROOT / "config" / "remote_qa_companies_overseas.yaml"
INDIA_OUT = ROOT / "config" / "remote_qa_companies_india.yaml"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def careers_url(name: str, region: str) -> str:
    slug = re.sub(r"[^a-z0-9]", "", name.lower())
    if region == "india":
        return f"https://www.{slug}.com/careers" if slug else ""
    return f"https://www.{slug}.com/careers"


def load_names(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_overseas_entry(name: str) -> dict:
    return {
        "id": f"overseas_{slugify(name)}",
        "name": name,
        "careers_url": careers_url(name, "overseas"),
        "ats": "website",
        "remote": True,
        "pays_usd": False,
        "currency": "overseas",
        "catalog_group": "overseas_global",
        "region": "global",
        "notes": "Remote QA-friendly; compensation typically in local/overseas currency (EUR, GBP, CAD, AUD, etc.)",
    }


def build_india_entry(name: str) -> dict:
    return {
        "id": f"india_{slugify(name)}",
        "name": name,
        "careers_url": careers_url(name, "india"),
        "ats": "website",
        "remote": True,
        "pays_usd": False,
        "currency": "INR",
        "catalog_group": "india",
        "region": "india",
        "notes": "QA/testing roles based in India; compensation typically in INR",
    }


def write_catalog(path: Path, meta: dict, companies: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump({"meta": meta, "companies": companies}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def main() -> int:
    existing = {n.lower() for n in load_names(EXISTING_NAMES)}
    overseas_names = load_names(OVERSEAS_NAMES)
    india_names = load_names(INDIA_NAMES)

    if len(overseas_names) != 1000:
        print(f"Expected 1000 overseas names, got {len(overseas_names)}", file=sys.stderr)
        return 1
    if len(india_names) != 500:
        print(f"Expected 500 India names, got {len(india_names)}", file=sys.stderr)
        return 1

    overseas_companies = []
    seen_ids: set[str] = set()
    for name in overseas_names:
        if name.lower() in existing:
            print(f"Skipping duplicate overseas name: {name}", file=sys.stderr)
            continue
        entry = build_overseas_entry(name)
        if entry["id"] in seen_ids:
            entry["id"] = f"{entry['id']}_{len(seen_ids)}"
        seen_ids.add(entry["id"])
        overseas_companies.append(entry)

    india_companies = []
    seen_ids.clear()
    for name in india_names:
        if name.lower() in existing:
            print(f"Skipping duplicate India name: {name}", file=sys.stderr)
            continue
        entry = build_india_entry(name)
        if entry["id"] in seen_ids:
            entry["id"] = f"{entry['id']}_{len(seen_ids)}"
        seen_ids.add(entry["id"])
        india_companies.append(entry)

    write_catalog(
        OVERSEAS_OUT,
        {
            "description": "1000 remote QA employers paying in overseas (non-USD) currencies",
            "total": len(overseas_companies),
            "currency": "overseas",
            "catalog_group": "overseas_global",
        },
        overseas_companies,
    )
    write_catalog(
        INDIA_OUT,
        {
            "description": "500 employers with QA/testing roles in India (INR)",
            "total": len(india_companies),
            "currency": "INR",
            "catalog_group": "india",
        },
        india_companies,
    )
    print(f"Wrote {len(overseas_companies)} overseas companies to {OVERSEAS_OUT}")
    print(f"Wrote {len(india_companies)} India companies to {INDIA_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
