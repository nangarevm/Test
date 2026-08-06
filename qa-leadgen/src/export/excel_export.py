"""Excel export for job requirements tracker and company directory."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src.models import CompanyContact, JobPosting, JobStatus


JOBS_COLUMNS = [
    "Company",
    "Role",
    "JD Summary",
    "Location",
    "Experience Level",
    "Employment Type",
    "Source",
    "Contact Email",
    "Posting Link",
    "Date Found",
    "Status",
]

COMPANY_COLUMNS = [
    "Company",
    "Website",
    "Industry",
    "Size",
    "General Contact Email",
    "Location",
    "Enrichment Source",
]

OUTREACH_COLUMNS = [
    "Job Key",
    "To Email",
    "Subject",
    "Status",
    "Sent At",
    "Opened At",
    "Replied At",
]


def _job_to_row(job: JobPosting) -> dict:
    return {
        "Company": job.company,
        "Role": job.role,
        "JD Summary": job.jd_summary,
        "Location": job.location,
        "Experience Level": job.experience_level,
        "Employment Type": job.employment_type,
        "Source": job.source,
        "Contact Email": job.contact_email or "",
        "Posting Link": job.posting_link,
        "Date Found": job.date_found.strftime("%Y-%m-%d %H:%M"),
        "Status": job.status.value if isinstance(job.status, JobStatus) else job.status,
        "_dedup_key": job.dedup_key,
    }


def _row_to_job(row: dict) -> JobPosting:
    status_val = row.get("Status", "New")
    try:
        status = JobStatus(status_val)
    except ValueError:
        status = JobStatus.NEW

    date_str = row.get("Date Found", "")
    try:
        date_found = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        date_found = datetime.utcnow()

    job = JobPosting(
        company=row.get("Company", ""),
        role=row.get("Role", ""),
        jd_text=row.get("JD Summary", ""),
        jd_summary=row.get("JD Summary", ""),
        location=row.get("Location", ""),
        experience_level=row.get("Experience Level", ""),
        employment_type=row.get("Employment Type", "Not specified") or "Not specified",
        source=row.get("Source", ""),
        contact_email=row.get("Contact Email") or None,
        posting_link=row.get("Posting Link", ""),
        date_found=date_found,
        status=status,
        dedup_key=row.get("_dedup_key", ""),
    )
    return job


def export_jobs_tracker(jobs: list[JobPosting], filepath: Path) -> None:
    rows = [_job_to_row(j) for j in jobs]
    df = pd.DataFrame(rows)
    display_cols = [c for c in JOBS_COLUMNS if c in df.columns]
    df[display_cols].to_excel(filepath, index=False, sheet_name="Job Requirements")
    _autosize_columns(filepath)


def load_jobs_tracker(filepath: Path) -> list[JobPosting]:
    if not filepath.exists():
        return []
    df = pd.read_excel(filepath, sheet_name="Job Requirements")
    jobs = []
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        row_dict["_dedup_key"] = f"{row_dict.get('Company', '').lower()}|{row_dict.get('Role', '').lower()}"
        jobs.append(_row_to_job(row_dict))
    return jobs


def merge_jobs(existing: list[JobPosting], new_jobs: list[JobPosting]) -> list[JobPosting]:
    by_key = {j.dedup_key: j for j in existing}
    for job in new_jobs:
        if job.dedup_key in by_key:
            existing_job = by_key[job.dedup_key]
            if not existing_job.contact_email and job.contact_email:
                existing_job.contact_email = job.contact_email
            if len(job.jd_text) > len(existing_job.jd_text):
                existing_job.jd_text = job.jd_text
                existing_job.jd_summary = job.jd_summary
        else:
            by_key[job.dedup_key] = job
    return list(by_key.values())


def export_company_directory(companies: list[CompanyContact], filepath: Path) -> None:
    rows = [
        {
            "Company": c.company,
            "Website": c.website,
            "Industry": c.industry,
            "Size": c.size,
            "General Contact Email": c.general_contact_email,
            "Location": c.location,
            "Enrichment Source": c.enrichment_source,
        }
        for c in companies
    ]
    df = pd.DataFrame(rows, columns=COMPANY_COLUMNS)
    df.to_excel(filepath, index=False, sheet_name="Company Directory")
    _autosize_columns(filepath)


def load_company_directory(filepath: Path) -> list[CompanyContact]:
    if not filepath.exists():
        return []
    df = pd.read_excel(filepath, sheet_name="Company Directory")
    companies = []
    for _, row in df.iterrows():
        companies.append(
            CompanyContact(
                company=row.get("Company", ""),
                website=row.get("Website", "") or "",
                industry=row.get("Industry", "") or "",
                size=row.get("Size", "") or "",
                general_contact_email=row.get("General Contact Email", "") or "",
                location=row.get("Location", "") or "",
                enrichment_source=row.get("Enrichment Source", "") or "",
            )
        )
    return companies


def update_job_status(filepath: Path, dedup_key: str, status: JobStatus) -> None:
    jobs = load_jobs_tracker(filepath)
    for job in jobs:
        if job.dedup_key == dedup_key:
            job.status = status
            break
    export_jobs_tracker(jobs, filepath)


def _autosize_columns(filepath: Path) -> None:
    from openpyxl import load_workbook

    wb = load_workbook(filepath)
    for ws in wb.worksheets:
        for column_cells in ws.columns:
            max_length = 0
            column_letter = column_cells[0].column_letter
            for cell in column_cells:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except Exception:
                    pass
            ws.column_dimensions[column_letter].width = min(max_length + 2, 60)
    wb.save(filepath)
