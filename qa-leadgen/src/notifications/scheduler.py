"""12-hour scheduler for fetch + Telegram report delivery."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import schedule
from rich.console import Console

console = Console()


def run_scheduled_loop(
    job_fn: Callable[[], None],
    interval_hours: float = 12,
    run_immediately: bool = True,
) -> None:
    """Run job_fn immediately (optional), then every interval_hours."""
    schedule.every(interval_hours).hours.do(job_fn)

    if run_immediately:
        console.print("[bold]Running initial job...[/bold]")
        job_fn()

    console.print(
        f"[green]Scheduler started. Running every {interval_hours} hours. Press Ctrl+C to stop.[/green]"
    )
    while True:
        schedule.run_pending()
        time.sleep(30)


def make_fetch_and_send_job(
    config: dict,
    data_dir: Path,
    fetch_fn: Callable[[], None],
    send_fn: Callable[[], bool],
) -> Callable[[], None]:
    def job() -> None:
        started = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        console.print(f"[bold cyan]Scheduled run started at {started}[/bold cyan]")
        try:
            fetch_fn()
            send_fn()
        except Exception as exc:
            console.print(f"[red]Scheduled job failed: {exc}[/red]")
        finished = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        console.print(f"[bold cyan]Scheduled run finished at {finished}[/bold cyan]")

    return job
