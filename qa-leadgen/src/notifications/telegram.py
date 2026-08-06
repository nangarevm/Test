"""Telegram bot integration for sending Excel reports."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import requests
from rich.console import Console

from src.export.excel_export import load_jobs_tracker
from src.models import WorkMode

console = Console()

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"


class TelegramNotifier:
    def __init__(self, config: dict) -> None:
        tg_cfg = config.get("telegram", {})
        self.enabled = tg_cfg.get("enabled", False)
        self.bot_token = tg_cfg.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = str(tg_cfg.get("chat_id") or os.getenv("TELEGRAM_CHAT_ID", ""))
        self.include_company_directory = tg_cfg.get("include_company_directory", True)
        self.message_template = tg_cfg.get(
            "message_template",
            "QA Lead-Gen report ({timestamp})\n"
            "Jobs tracked: {job_count}\n"
            "Remote: {remote_count} | Hybrid: {hybrid_count} | Office: {office_count}\n"
            "Freelance/contract: {freelance_count}\n"
            "New: {new_count} | Contacted: {contacted_count}",
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def is_enabled(self) -> bool:
        return bool(self.enabled and self.is_configured)

    def _api_url(self, method: str) -> str:
        return TELEGRAM_API_BASE.format(token=self.bot_token, method=method)

    def send_message(self, text: str, chat_id: str | None = None) -> bool:
        target = chat_id or self.chat_id
        if not self.bot_token or not target:
            console.print("[red]Telegram not configured. Set bot_token and chat_id.[/red]")
            return False
        try:
            resp = requests.post(
                self._api_url("sendMessage"),
                json={"chat_id": target, "text": text},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                console.print(f"[red]Telegram API error: {data}[/red]")
                return False
            return True
        except Exception as exc:
            console.print(f"[red]Failed to send Telegram message: {exc}[/red]")
            return False

    def send_document(self, filepath: Path, caption: str = "") -> bool:
        if not self.is_configured:
            console.print("[red]Telegram not configured. Set telegram.enabled, bot_token, and chat_id.[/red]")
            return False
        if not filepath.exists():
            console.print(f"[red]File not found: {filepath}[/red]")
            return False

        try:
            with open(filepath, "rb") as doc:
                resp = requests.post(
                    self._api_url("sendDocument"),
                    data={"chat_id": self.chat_id, "caption": caption[:1024]},
                    files={"document": (filepath.name, doc)},
                    timeout=120,
                )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                console.print(f"[red]Telegram API error: {data}[/red]")
                return False
            console.print(f"[green]Sent {filepath.name} to Telegram[/green]")
            return True
        except Exception as exc:
            console.print(f"[red]Failed to send document: {exc}[/red]")
            return False

    def build_summary(self, jobs_file: Path) -> str:
        jobs = load_jobs_tracker(jobs_file) if jobs_file.exists() else []
        freelance = sum(
            1 for j in jobs if j.employment_type in {"Freelance", "Contract", "Part-time"}
        )
        remote = sum(1 for j in jobs if j.work_mode == WorkMode.REMOTE.value)
        hybrid = sum(1 for j in jobs if j.work_mode == WorkMode.HYBRID.value)
        office = sum(1 for j in jobs if j.work_mode == WorkMode.OFFICE.value)
        status_counts: dict[str, int] = {}
        for job in jobs:
            status_counts[job.status.value] = status_counts.get(job.status.value, 0) + 1

        return self.message_template.format(
            timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            job_count=len(jobs),
            remote_count=remote,
            hybrid_count=hybrid,
            office_count=office,
            freelance_count=freelance,
            new_count=status_counts.get("New", 0),
            contacted_count=status_counts.get("Contacted", 0),
            responded_count=status_counts.get("Responded", 0),
            closed_count=status_counts.get("Closed", 0),
        )

    def send_reports(self, config: dict, data_dir: Path) -> bool:
        if not self.is_configured:
            return False

        jobs_file = data_dir / config["output"]["jobs_tracker"]
        company_file = data_dir / config["output"]["company_directory"]

        if not jobs_file.exists():
            console.print("[yellow]No jobs tracker file found. Run fetch first.[/yellow]")
            return self.send_message("QA Lead-Gen: No job tracker file found yet. Run fetch first.")

        summary = self.build_summary(jobs_file)
        if not self.send_message(summary):
            return False

        jobs_ok = self.send_document(jobs_file, caption="Job Requirements Tracker")
        company_ok = True
        if self.include_company_directory and company_file.exists():
            company_ok = self.send_document(company_file, caption="Company Directory")

        return jobs_ok and company_ok
