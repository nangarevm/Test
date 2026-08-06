"""Interactive outreach review workflow and tracking."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from src.export.excel_export import load_jobs_tracker, update_job_status
from src.models import EmailStatus, JobStatus, OutreachEmail
from src.outreach.email_sender import EmailSender
from src.outreach.templates import render_email

console = Console()


class OutreachManager:
    def __init__(self, config: dict, data_dir: Path) -> None:
        self.config = config
        self.data_dir = data_dir
        self.tracker_file = data_dir / "outreach_tracker.json"
        self.jobs_file = data_dir / config.get("output", {}).get(
            "jobs_tracker", "job_requirements_tracker.xlsx"
        )
        self.sender = EmailSender(config, data_dir)
        self.outreach_log: list[dict] = self._load_log()

    def _load_log(self) -> list[dict]:
        if self.tracker_file.exists():
            return json.loads(self.tracker_file.read_text())
        return []

    def _save_log(self) -> None:
        self.tracker_file.write_text(json.dumps(self.outreach_log, indent=2, default=str))

    def _already_contacted(self, dedup_key: str) -> bool:
        return any(
            e.get("job_dedup_key") == dedup_key and e.get("status") == EmailStatus.SENT.value
            for e in self.outreach_log
        )

    def review_and_send(self, dry_run: bool = False) -> None:
        jobs = load_jobs_tracker(self.jobs_file)
        contactable = [
            j
            for j in jobs
            if j.status in (JobStatus.NEW, JobStatus.CONTACTED)
            and (j.contact_email or self._lookup_company_email(j.company))
            and not self._already_contacted(j.dedup_key)
        ]

        if not contactable:
            console.print("[yellow]No jobs ready for outreach (need contact email and New status).[/yellow]")
            return

        console.print(f"[bold]Found {len(contactable)} jobs ready for outreach.[/bold]")
        console.print(f"Daily send limit remaining: {self.sender.rate_limiter.remaining}")

        for job in contactable:
            to_email = job.contact_email or self._lookup_company_email(job.company)
            if not to_email:
                continue

            subject, body = render_email(
                company=job.company,
                role=job.role,
                jd_text=job.jd_text,
                user_config=self.config.get("user", {}),
            )

            console.print(Panel(
                f"[bold]To:[/bold] {to_email}\n"
                f"[bold]Subject:[/bold] {subject}\n\n{body}",
                title=f"{job.company} — {job.role}",
                border_style="blue",
            ))

            action = Prompt.ask(
                "Action",
                choices=["send", "edit", "skip", "quit"],
                default="skip",
            )

            if action == "quit":
                break
            if action == "skip":
                continue

            if action == "edit":
                console.print("[dim]Enter new subject (or press Enter to keep):[/dim]")
                new_subject = Prompt.ask("Subject", default=subject)
                console.print("[dim]Enter new body (type END on its own line to finish):[/dim]")
                lines = []
                while True:
                    line = input()
                    if line.strip() == "END":
                        break
                    lines.append(line)
                if lines:
                    body = "\n".join(lines)
                subject = new_subject

            if action in ("send", "edit"):
                outreach = OutreachEmail(
                    job_dedup_key=job.dedup_key,
                    to_email=to_email,
                    subject=subject,
                    body=body,
                )
                if self.sender.send(outreach, dry_run=dry_run):
                    self.outreach_log.append({
                        "job_dedup_key": job.dedup_key,
                        "to_email": to_email,
                        "subject": subject,
                        "status": outreach.status.value,
                        "sent_at": str(outreach.sent_at),
                    })
                    self._save_log()
                    if not dry_run:
                        update_job_status(self.jobs_file, job.dedup_key, JobStatus.CONTACTED)

    def _lookup_company_email(self, company: str) -> str | None:
        company_file = self.data_dir / self.config.get("output", {}).get(
            "company_directory", "company_directory.xlsx"
        )
        if not company_file.exists():
            return None
        from src.export.excel_export import load_company_directory

        for c in load_company_directory(company_file):
            if c.company.lower() == company.lower() and c.general_contact_email:
                return c.general_contact_email
        return None

    def show_stats(self) -> None:
        total = len(self.outreach_log)
        sent = sum(1 for e in self.outreach_log if e.get("status") == EmailStatus.SENT.value)
        console.print(f"Outreach stats: {sent} sent / {total} total logged")
        console.print(f"Remaining today: {self.sender.rate_limiter.remaining}")
