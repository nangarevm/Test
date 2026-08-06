"""Excel export with daily sheets and master tracker."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd

from src.models import CompanyContact, JobPosting, JobStatus

MASTER_SHEET = "All Jobs"
LEGACY_SHEET = "Job Requirements"
DAILY_SUMMARY_SHEET = "Daily Summary"
OVERSEAS_DIRECTORY_SHEET = "Overseas Job Boards"

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

DAILY_SUMMARY_COLUMNS = [
    "Date",
    "Jobs Found Today",
    "Freelance/Contract",
    "Top Sources",
    "Total All-Time Jobs",
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


def _jobs_to_df(jobs: list[JobPosting]) -> pd.DataFrame:
    rows = [_job_to_row(j) for j in jobs]
    df = pd.DataFrame(rows)
    display_cols = [c for c in JOBS_COLUMNS if c in df.columns or not rows]
    if not df.empty:
        return df[display_cols]
    return pd.DataFrame(columns=JOBS_COLUMNS)


def _row_to_job(row: dict) -> JobPosting:
    status_val = row.get("Status", "New")
    try:
        status = JobStatus(status_val)
    except ValueError:
        status = JobStatus.NEW

    date_str = row.get("Date Found", "")
    try:
        date_found = datetime.strptime(str(date_str), "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        date_found = datetime.utcnow()

    return JobPosting(
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


def _sheet_name_for_day(day: date | None = None) -> str:
    return (day or date.today()).strftime("%Y-%m-%d")


def _read_existing_sheets(filepath: Path) -> dict[str, pd.DataFrame]:
    if not filepath.exists():
        return {}
    try:
        book = pd.read_excel(filepath, sheet_name=None)
        return {str(name): df for name, df in book.items()}
    except Exception:
        return {}


def _is_jobs_sheet(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        return False
    columns = {str(col).strip().lower() for col in df.columns}
    return {"company", "role"}.issubset(columns)


def _resolve_jobs_sheet(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    """Pick the master jobs sheet, supporting legacy and migrated workbooks."""
    for sheet_name in (MASTER_SHEET, LEGACY_SHEET):
        df = sheets.get(sheet_name)
        if _is_jobs_sheet(df):
            return df

    skip = {
        DAILY_SUMMARY_SHEET.lower(),
        OVERSEAS_DIRECTORY_SHEET.lower(),
        "company directory",
    }
    for name, df in sheets.items():
        if str(name).strip().lower() in skip:
            continue
        if _is_jobs_sheet(df):
            return df
    return None


def _build_daily_summary_row(
    day: date,
    daily_jobs: list[JobPosting],
    total_jobs: int,
) -> dict:
    freelance = sum(
        1 for j in daily_jobs if j.employment_type in {"Freelance", "Contract", "Part-time"}
    )
    sources: dict[str, int] = {}
    for job in daily_jobs:
        sources[job.source] = sources.get(job.source, 0) + 1
    top = ", ".join(f"{k} ({v})" for k, v in sorted(sources.items(), key=lambda x: -x[1])[:5])
    return {
        "Date": day.isoformat(),
        "Jobs Found Today": len(daily_jobs),
        "Freelance/Contract": freelance,
        "Top Sources": top or "n/a",
        "Total All-Time Jobs": total_jobs,
    }


def _update_daily_summary(existing: pd.DataFrame | None, row: dict) -> pd.DataFrame:
    df = existing.copy() if existing is not None and not existing.empty else pd.DataFrame(columns=DAILY_SUMMARY_COLUMNS)
    df = df[df["Date"].astype(str) != row["Date"]] if not df.empty and "Date" in df.columns else df
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    return df.sort_values("Date", ascending=False).reset_index(drop=True)


def export_jobs_tracker(
    jobs: list[JobPosting],
    filepath: Path,
    *,
    daily_jobs: list[JobPosting] | None = None,
    export_day: date | None = None,
) -> str:
    """
    Export master sheet + one sheet per day + daily summary.
    Returns the daily sheet name written.
    """
    day = export_day or date.today()
    daily_sheet = _sheet_name_for_day(day)
    sheets = _read_existing_sheets(filepath)

    master_df = _jobs_to_df(jobs)
    sheets[MASTER_SHEET] = master_df

    snapshot = daily_jobs if daily_jobs is not None else jobs
    sheets[daily_sheet] = _jobs_to_df(snapshot)

    summary_row = _build_daily_summary_row(day, snapshot, len(jobs))
    sheets[DAILY_SUMMARY_SHEET] = _update_daily_summary(sheets.get(DAILY_SUMMARY_SHEET), summary_row)

    # Drop legacy sheet name if migrating
    sheets.pop(LEGACY_SHEET, None)

    filepath.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        sheet_order = [MASTER_SHEET, DAILY_SUMMARY_SHEET]
        for name, df in sheets.items():
            if name not in sheet_order:
                sheet_order.append(name)
        for name in sheet_order:
            if name in sheets:
                sheets[name].to_excel(writer, sheet_name=name, index=False)

    _autosize_columns(filepath)
    return daily_sheet


def load_jobs_tracker(filepath: Path) -> list[JobPosting]:
    if not filepath.exists():
        return []
    sheets = _read_existing_sheets(filepath)
    df = _resolve_jobs_sheet(sheets)
    if df is None:
        return []

    jobs = []
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        if not row_dict.get("_dedup_key"):
            company = str(row_dict.get("Company", "")).lower()
            role = str(row_dict.get("Role", "")).lower()
            row_dict["_dedup_key"] = f"{company}|{role}"
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


def export_overseas_directory(platforms: list, filepath: Path) -> None:
    """Write/update overseas job boards reference sheet in the tracker workbook."""
    rows = [
        {
            "Country/Region": getattr(p, "country", "") or "Global",
            "Platform": p.name,
            "Category": p.category,
            "URL": p.url,
            "Auto-Fetch": "Yes" if p.is_fetchable else "Manual",
            "Adapter": p.adapter,
            "Notes": p.notes,
        }
        for p in platforms
    ]
    df = pd.DataFrame(rows)

    sheets = _read_existing_sheets(filepath)
    sheets[OVERSEAS_DIRECTORY_SHEET] = df

    filepath.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for name, sheet_df in sheets.items():
            sheet_df.to_excel(writer, sheet_name=name, index=False)
    _autosize_columns(filepath)


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

    sheets = _read_existing_sheets(filepath)
    sheets["Company Directory"] = df

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for name, sheet_df in sheets.items():
            sheet_df.to_excel(writer, sheet_name=name, index=False)
    _autosize_columns(filepath)


def load_company_directory(filepath: Path) -> list[CompanyContact]:
    if not filepath.exists():
        return []
    sheets = _read_existing_sheets(filepath)
    if "Company Directory" not in sheets:
        return []
    df = sheets["Company Directory"]
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
