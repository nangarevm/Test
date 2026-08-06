#!/usr/bin/env python3
"""Generate remote_qa_companies.yaml with exactly 500 unique USD-paying employers."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "config" / "remote_qa_companies.yaml"
TARGET_COUNT = 500

# (id, name, ats, ats_slug|None, region, careers_url|None)
Entry = tuple[str, str, str, str | None, str, str | None]

PRIORITY: list[Entry] = [
    ("ineight", "InEight", "website", None, "usa", "https://ineight.com/company/careers/"),
    ("rainforest_qa", "Rainforest QA", "website", None, "global", "https://www.rainforestqa.com/careers"),
    ("xapo_bank", "Xapo Bank", "website", None, "global", "https://www.xapobank.com/en/careers"),
    ("bamboohr", "BambooHR", "website", None, "usa", "https://www.bamboohr.com/careers/"),
    ("aurora_labs", "Aurora Labs", "website", None, "global", "https://www.auroralabs.com/career"),
    ("synack", "Synack", "greenhouse", "synack", "usa", None),
    ("bloomreach", "Bloomreach", "greenhouse", "bloomreach", "global", None),
    ("brillio", "Brillio", "website", None, "global", "https://www.brillio.com/careers/"),
    ("the_block", "The Block", "lever", "theblockcrypto", "global", None),
    ("allata", "Allata", "website", None, "usa", "https://www.allata.com/careers/"),
    ("deep_consulting_solutions", "Deep Consulting Solutions", "website", None, "global", "https://deepconsulting.solutions/"),
    ("soar_financials", "Soar Financials", "website", None, "usa", "https://www.soarfinancial.com/"),
    ("kodify_media_group", "Kodify Media Group", "recruitee", "kodify", "europe", None),
    ("wealthbox_crm", "Wealthbox CRM", "website", None, "usa", "https://www.wealthbox.com/careers/"),
    ("xm", "XM", "website", None, "global", "https://www.xm.com/about-us/careers/"),
    ("close", "Close", "website", None, "global", "https://close.com/careers"),
    ("toptal", "Toptal", "lever", "toptal", "global", None),
    ("cortes_23", "Cortes 23", "website", None, "usa", "https://cortes23.com/"),
]

# fmt: off
CATALOG: list[Entry] = [
    # --- remote-first SaaS ---
    ("gitlab", "GitLab", "greenhouse", "gitlab", "global", None),
    ("automattic", "Automattic", "website", None, "global", "https://automattic.com/work-with-us/"),
    ("zapier", "Zapier", "greenhouse", "zapier", "global", None),
    ("shopify", "Shopify", "greenhouse", "shopify", "global", None),
    ("atlassian", "Atlassian", "website", None, "global", "https://www.atlassian.com/company/careers"),
    ("notion", "Notion", "greenhouse", "notion", "global", None),
    ("figma", "Figma", "greenhouse", "figma", "global", None),
    ("asana", "Asana", "greenhouse", "asana", "global", None),
    ("airtable", "Airtable", "greenhouse", "airtable", "global", None),
    ("monday_com", "monday.com", "greenhouse", "mondaydotcom", "global", None),
    ("clickup", "ClickUp", "greenhouse", "clickup", "global", None),
    ("miro", "Miro", "greenhouse", "miro", "global", None),
    ("canva", "Canva", "greenhouse", "canva", "global", None),
    ("hubspot", "HubSpot", "greenhouse", "hubspot", "global", None),
    ("zendesk", "Zendesk", "greenhouse", "zendesk", "global", None),
    ("intercom", "Intercom", "greenhouse", "intercom", "global", None),
    ("freshworks", "Freshworks", "greenhouse", "freshworks", "global", None),
    ("calendly", "Calendly", "greenhouse", "calendly", "global", None),
    ("loom", "Loom", "greenhouse", "loom", "global", None),
    ("dropbox", "Dropbox", "greenhouse", "dropbox", "global", None),
    ("box", "Box", "greenhouse", "box", "global", None),
    ("docusign", "DocuSign", "greenhouse", "docusign", "global", None),
    ("twilio", "Twilio", "greenhouse", "twilio", "global", None),
    ("typeform", "Typeform", "greenhouse", "typeform", "global", None),
    ("webflow", "Webflow", "greenhouse", "webflow", "global", None),
    ("squarespace", "Squarespace", "greenhouse", "squarespace", "global", None),
    ("wix", "Wix", "greenhouse", "wix", "global", None),
    ("smartsheet", "Smartsheet", "greenhouse", "smartsheet", "global", None),
    ("pipedrive", "Pipedrive", "greenhouse", "pipedrive", "global", None),
    ("gong", "Gong", "greenhouse", "gong", "global", None),
    ("outreach", "Outreach", "greenhouse", "outreach", "global", None),
    ("salesloft", "Salesloft", "greenhouse", "salesloft", "global", None),
    ("pendo", "Pendo", "greenhouse", "pendo", "global", None),
    ("gainsight", "Gainsight", "greenhouse", "gainsight", "global", None),
    ("productboard", "Productboard", "greenhouse", "productboard", "global", None),
    ("linear", "Linear", "greenhouse", "linear", "global", None),
    ("basecamp", "Basecamp", "website", None, "global", "https://basecamp.com/about/jobs"),
    ("doist", "Doist", "website", None, "global", "https://doist.com/careers"),
    ("buffer", "Buffer", "website", None, "global", "https://buffer.com/journey"),
    ("toggl", "Toggl", "website", None, "global", "https://toggl.com/jobs/"),
    ("hotjar", "Hotjar", "greenhouse", "hotjar", "global", None),
    ("fullstory", "FullStory", "greenhouse", "fullstory", "global", None),
    ("heap", "Heap", "greenhouse", "heap", "global", None),
    ("amplitude", "Amplitude", "greenhouse", "amplitude", "global", None),
    ("mixpanel", "Mixpanel", "greenhouse", "mixpanel", "global", None),
    ("segment", "Segment", "greenhouse", "segment", "global", None),
    ("rudderstack", "RudderStack", "greenhouse", "rudderstack", "global", None),
    ("hightouch", "Hightouch", "greenhouse", "hightouch", "global", None),
    ("census", "Census", "greenhouse", "census", "global", None),
    ("fivetran", "Fivetran", "greenhouse", "fivetran", "global", None),
    ("airbyte", "Airbyte", "greenhouse", "airbyte", "global", None),
    ("dbt_labs", "dbt Labs", "greenhouse", "dbtlabs", "global", None),
    ("snowflake", "Snowflake", "greenhouse", "snowflake", "global", None),
    ("databricks", "Databricks", "greenhouse", "databricks", "global", None),
    ("confluent", "Confluent", "greenhouse", "confluent", "global", None),
    ("elastic", "Elastic", "greenhouse", "elastic", "global", None),
    ("mongodb", "MongoDB", "greenhouse", "mongodb", "global", None),
    ("cockroach_labs", "Cockroach Labs", "greenhouse", "cockroachlabs", "global", None),
    ("planetscale", "PlanetScale", "greenhouse", "planetscale", "global", None),
    ("supabase", "Supabase", "greenhouse", "supabase", "global", None),
    ("neon", "Neon", "greenhouse", "neon", "global", None),
    ("hasura", "Hasura", "greenhouse", "hasura", "global", None),
    ("retool", "Retool", "greenhouse", "retool", "global", None),
    ("workato", "Workato", "greenhouse", "workato", "global", None),
    ("tray_io", "Tray.io", "greenhouse", "trayio", "global", None),
    ("coda", "Coda", "greenhouse", "coda", "global", None),
    ("lattice", "Lattice", "greenhouse", "lattice", "global", None),
    ("gusto", "Gusto", "greenhouse", "gusto", "usa", None),
    ("rippling", "Rippling", "greenhouse", "rippling", "usa", None),
    ("deel", "Deel", "greenhouse", "deel", "global", None),
    ("remote_com", "Remote", "greenhouse", "remote", "global", None),
    ("oyster_hr", "Oyster", "greenhouse", "oysterhr", "global", None),
    ("papaya_global", "Papaya Global", "greenhouse", "papayaglobal", "global", None),
    ("justworks", "Justworks", "greenhouse", "justworks", "usa", None),
    ("namely", "Namely", "greenhouse", "namely", "usa", None),
    ("15five", "15Five", "greenhouse", "15five", "global", None),
    ("culture_amp", "Culture Amp", "greenhouse", "cultureamp", "global", None),
    ("leapsome", "Leapsome", "greenhouse", "leapsome", "global", None),
    ("personio", "Personio", "greenhouse", "personio", "europe", None),
    ("hibob", "HiBob", "greenhouse", "hibob", "global", None),
    ("ashby", "Ashby", "greenhouse", "ashby", "global", None),
    ("greenhouse_software", "Greenhouse Software", "greenhouse", "greenhouse", "usa", None),
    ("lever", "Lever", "greenhouse", "lever", "usa", None),
    ("gem", "Gem", "greenhouse", "gem", "global", None),
    ("beamery", "Beamery", "greenhouse", "beamery", "global", None),
    ("eightfold_ai", "Eightfold AI", "greenhouse", "eightfold", "global", None),
    ("phenom", "Phenom", "greenhouse", "phenom", "global", None),
    ("icims", "iCIMS", "greenhouse", "icims", "usa", None),
    ("smartrecruiters", "SmartRecruiters", "greenhouse", "smartrecruiters", "global", None),
    ("jobvite", "Jobvite", "greenhouse", "jobvite", "usa", None),
    ("breezy_hr", "Breezy HR", "website", None, "global", "https://breezy.hr/careers"),
    ("workable", "Workable", "greenhouse", "workable", "global", None),
    ("recruitee", "Recruitee", "website", None, "europe", "https://recruitee.com/careers"),
    ("teamtailor", "Teamtailor", "website", None, "europe", "https://career.teamtailor.com/"),
    ("factorial", "Factorial", "greenhouse", "factorial", "europe", None),
]
# fmt: on

KNOWN_OVERRIDES: dict[str, Entry] = {
    e[0]: e for e in PRIORITY + CATALOG
}

# Map display names to override ids
NAME_TO_ID = {
    "monday.com": "monday_com",
    "Remote": "remote_com",
    "dbt Labs": "dbt_labs",
    "Tray.io": "tray_io",
    "15Five": "15five",
    "HiBob": "hibob",
    "iCIMS": "icims",
}


def slugify(name: str) -> str:
    key = NAME_TO_ID.get(name, name)
    slug = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    return slug


def careers_url_for(name: str, ats: str, ats_slug: str | None, explicit: str | None) -> str:
    if explicit:
        return explicit
    if ats == "greenhouse" and ats_slug:
        return f"https://boards.greenhouse.io/{ats_slug}"
    if ats == "lever" and ats_slug:
        return f"https://jobs.lever.co/{ats_slug}"
    if ats == "recruitee" and ats_slug:
        return f"https://{ats_slug}.recruitee.com/"
    domain = re.sub(r"[^a-z0-9]", "", name.lower())
    return f"https://www.{domain}.com/careers"


def entry_for_name(name: str) -> Entry:
    slug = slugify(name)
    if slug in KNOWN_OVERRIDES:
        return KNOWN_OVERRIDES[slug]
    for entry in KNOWN_OVERRIDES.values():
        if entry[1].lower() == name.lower():
            return entry
    return (slug, name, "website", None, "global", f"https://www.{slug.replace('_', '')}.com/careers")


def build_catalog() -> list[dict]:
    names_file = ROOT / "scripts" / "remote_qa_company_names.txt"
    names = [line.strip() for line in names_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    companies: list[dict] = []
    seen: set[str] = set()
    for name in names:
        entry = entry_for_name(name)
        cid, cname, ats, ats_slug, region, explicit_url = entry
        if cid in seen:
            continue
        seen.add(cid)
        companies.append(
            {
                "id": cid,
                "name": cname,
                "careers_url": careers_url_for(cname, ats, ats_slug, explicit_url),
                "ats": ats,
                **({"ats_slug": ats_slug} if ats_slug else {}),
                "remote": True,
                "pays_usd": True,
                "region": region,
                "notes": "Remote QA-friendly employer; USD compensation common for global hires",
            }
        )
    return companies


def main() -> int:
    companies = build_catalog()
    if len(companies) != TARGET_COUNT:
        print(f"Expected {TARGET_COUNT} companies, got {len(companies)}", file=sys.stderr)
        return 1

    ats_fetchable = sum(1 for c in companies if c.get("ats") in {"greenhouse", "lever", "recruitee"} and c.get("ats_slug"))
    payload = {
        "meta": {
            "description": "500 remote-friendly employers for QA roles with USD pay globally",
            "total": len(companies),
            "remote": True,
            "pays_usd": True,
            "ats_fetchable": ats_fetchable,
        },
        "companies": companies,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        yaml.dump(payload, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"Wrote {len(companies)} companies to {OUTPUT} ({ats_fetchable} ATS-fetchable)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
