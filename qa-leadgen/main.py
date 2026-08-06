#!/usr/bin/env python3
"""QA Staffing Lead-Gen & Outreach Tool — CLI entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.aggregator import aggregate_jobs
from src.config import ensure_output_dir, load_config
from src.enrichment.company_enricher import CompanyEnricher
from src.export.excel_export import (
    export_company_directory,
    export_jobs_tracker,
    export_overseas_directory,
    load_company_directory,
    load_jobs_tracker,
    merge_jobs,
)
from src.aggregator.platforms_registry import load_platforms
from src.outreach.tracker import OutreachManager

console = Console()


def _run_fetch(ctx: click.Context, all_qa: bool = False) -> None:
    config = ctx.obj["config"]
    if all_qa:
        config.setdefault("search", {})["only_freelance"] = False
    data_dir = ctx.obj["data_dir"]
    jobs_file = data_dir / config["output"]["jobs_tracker"]

    console.print("[bold]Starting job aggregation...[/bold]")
    new_jobs = aggregate_jobs(config)

    existing = load_jobs_tracker(jobs_file) if jobs_file.exists() else []
    merged = merge_jobs(existing, new_jobs)
    daily_sheet = export_jobs_tracker(merged, jobs_file, daily_jobs=new_jobs)
    export_overseas_directory(load_platforms(), jobs_file)
    console.print(f"[green]Saved {len(merged)} jobs to {jobs_file}[/green]")
    console.print(f"  Daily sheet: {daily_sheet} ({len(new_jobs)} jobs found this run)")


@click.group()
@click.option("--config", "-c", default="config.yaml", help="Path to config file")
@click.pass_context
def cli(ctx: click.Context, config: str) -> None:
    """QA Staffing Lead-Gen & Outreach Tool."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(PROJECT_ROOT / config)
    ctx.obj["data_dir"] = ensure_output_dir(ctx.obj["config"])


@cli.command()
@click.option("--all-qa", is_flag=True, help="Include full-time QA jobs, not just freelance/contract")
@click.pass_context
def fetch(ctx: click.Context, all_qa: bool) -> None:
    """Aggregate QA job postings from configured sources."""
    _run_fetch(ctx, all_qa=all_qa)
    config = ctx.obj["config"]
    data_dir = ctx.obj["data_dir"]
    jobs_file = data_dir / config["output"]["jobs_tracker"]
    merged = load_jobs_tracker(jobs_file)

    freelance = sum(1 for j in merged if j.employment_type in {"Freelance", "Contract", "Part-time"})
    if merged:
        console.print(f"  Employment breakdown: {freelance} freelance/contract/part-time, {len(merged) - freelance} other")
        for j in merged[:10]:
            console.print(
                f"    [{j.work_mode}] [{j.employment_type}] {j.company} — {j.role} ({j.source})"
            )
        if len(merged) > 10:
            console.print(f"    ... and {len(merged) - 10} more")


@cli.command("platforms")
@click.option("--category", "-g", default=None, help="Filter by category (e.g. general_remote)")
@click.option("--fetchable-only", is_flag=True, help="Show only platforms with automated feeds")
@click.pass_context
def platforms_cmd(ctx: click.Context, category: str | None, fetchable_only: bool) -> None:
    """List all 100 registered remote job platforms."""
    from rich.table import Table

    from src.aggregator.platforms_registry import (
        category_label,
        group_platforms,
        load_platforms,
        resolve_enabled_platforms,
    )

    config = ctx.obj["config"]
    all_platforms = load_platforms()
    enabled = {p.id for p in resolve_enabled_platforms(config)}

    if category:
        filtered = [p for p in all_platforms if p.category == category]
        groups = {category: filtered}
    else:
        filtered = all_platforms
        groups = group_platforms(filtered)

    table = Table(title=f"Job Platforms ({len(all_platforms)} registered)")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Category")
    table.add_column("Adapter")
    table.add_column("Enabled")
    table.add_column("Country", style="dim")
    table.add_column("URL")

    for cat, items in sorted(groups.items(), key=lambda x: category_label(x[0])):
        for p in items:
            if fetchable_only and not p.is_fetchable:
                continue
            table.add_row(
                p.id,
                p.name,
                category_label(p.category),
                p.adapter + (" *" if p.requires_api_key else ""),
                "yes" if p.id in enabled else "no",
                getattr(p, "country", "") or "Global",
                p.url,
            )
    console.print(table)
    fetchable = sum(1 for p in all_platforms if p.is_fetchable)
    console.print(
        f"\n{fetchable} platforms have automated adapters; "
        f"{len(enabled)} enabled in current config."
    )


@cli.command()
@click.pass_context
def enrich(ctx: click.Context) -> None:
    """Enrich companies without public contact emails."""
    config = ctx.obj["config"]
    data_dir = ctx.obj["data_dir"]
    jobs_file = data_dir / config["output"]["jobs_tracker"]
    company_file = data_dir / config["output"]["company_directory"]

    if not jobs_file.exists():
        console.print("[red]Run 'fetch' first to collect job postings.[/red]")
        return

    jobs = load_jobs_tracker(jobs_file)
    enricher = CompanyEnricher(config)
    new_contacts = enricher.enrich_companies(jobs)

    existing = load_company_directory(company_file) if company_file.exists() else []
    by_name = {c.company.lower(): c for c in existing}
    for contact in new_contacts:
        by_name[contact.company.lower()] = contact

    export_company_directory(list(by_name.values()), company_file)
    console.print(f"[green]Saved {len(by_name)} companies to {company_file}[/green]")


@cli.command()
@click.option("--dry-run", is_flag=True, help="Preview sends without actually emailing")
@click.pass_context
def outreach(ctx: click.Context, dry_run: bool) -> None:
    """Review and send personalized outreach emails."""
    config = ctx.obj["config"]
    data_dir = ctx.obj["data_dir"]
    manager = OutreachManager(config, data_dir)
    manager.review_and_send(dry_run=dry_run)


@cli.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """Show outreach statistics."""
    config = ctx.obj["config"]
    data_dir = ctx.obj["data_dir"]
    manager = OutreachManager(config, data_dir)
    manager.show_stats()

    jobs_file = data_dir / config["output"]["jobs_tracker"]
    if jobs_file.exists():
        jobs = load_jobs_tracker(jobs_file)
        status_counts: dict[str, int] = {}
        for j in jobs:
            status_counts[j.status.value] = status_counts.get(j.status.value, 0) + 1
        console.print(f"Job tracker: {len(jobs)} total")
        for status, count in sorted(status_counts.items()):
            console.print(f"  {status}: {count}")


@cli.command()
@click.pass_context
def run_all(ctx: click.Context) -> None:
    """Fetch jobs, enrich contacts, then start outreach review."""
    ctx.invoke(fetch)
    if ctx.obj["config"].get("enrichment", {}).get("enabled", True):
        ctx.invoke(enrich)
    ctx.invoke(outreach)


@cli.group()
@click.pass_context
def telegram(ctx: click.Context) -> None:
    """Telegram reports, bot commands, and scheduled scanning."""
    pass


@telegram.command("setup")
@click.option("--timeout", default=120, help="Seconds to wait for you to message the bot")
@click.pass_context
def telegram_setup_cmd(ctx: click.Context, timeout: int) -> None:
    """Discover your chat ID — message your bot, then we save it to .env."""
    from src.notifications.telegram_setup import run_setup

    if run_setup(ctx.obj["config"], PROJECT_ROOT, timeout=timeout):
        console.print("\n[bold]Next steps:[/bold]")
        console.print("  python main.py telegram test")
        console.print("  python main.py automate start")
    else:
        raise SystemExit(1)


@telegram.command("test")
@click.pass_context
def telegram_test(ctx: click.Context) -> None:
    """Send a test message to verify Telegram configuration."""
    from src.notifications.telegram import TelegramNotifier

    notifier = TelegramNotifier(ctx.obj["config"])
    if notifier.send_message("QA Lead-Gen Telegram integration is working."):
        console.print("[green]Test message sent successfully.[/green]")
    else:
        raise SystemExit(1)


@telegram.command("send")
@click.option("--fetch-first", is_flag=True, help="Run fetch before sending Excel files")
@click.option("--all-qa", is_flag=True, help="Include full-time QA when fetching first")
@click.pass_context
def telegram_send(ctx: click.Context, fetch_first: bool, all_qa: bool) -> None:
    """Send current Excel tracker files to Telegram now."""
    from src.notifications.telegram import TelegramNotifier

    if fetch_first:
        _run_fetch(ctx, all_qa=all_qa)

    notifier = TelegramNotifier(ctx.obj["config"])
    ok = notifier.send_reports(ctx.obj["config"], ctx.obj["data_dir"])
    if not ok:
        raise SystemExit(1)


@telegram.command("run")
@click.option("--interval", type=float, default=None, help="Hours between runs (default: config value)")
@click.option("--no-immediate", is_flag=True, help="Skip the initial run; wait for first interval")
@click.option("--all-qa", is_flag=True, help="Include full-time QA roles when fetching")
@click.pass_context
def telegram_run(ctx: click.Context, interval: float | None, no_immediate: bool, all_qa: bool) -> None:
    """Fetch jobs and send Excel to Telegram every 12 hours (configurable)."""
    from src.notifications.scheduler import make_fetch_and_send_job, run_scheduled_loop
    from src.notifications.telegram import TelegramNotifier

    config = ctx.obj["config"]
    data_dir = ctx.obj["data_dir"]
    tg_cfg = config.get("telegram", {})
    hours = interval or tg_cfg.get("interval_hours", 12)

    notifier = TelegramNotifier(config)
    if not notifier.is_configured:
        console.print(
            "[red]Telegram not configured.[/red]\n"
            "Set telegram.enabled: true, bot_token, and chat_id in config.yaml\n"
            "or TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID in .env"
        )
        raise SystemExit(1)

    def fetch_job() -> None:
        _run_fetch(ctx, all_qa=all_qa)

    def send_job() -> bool:
        return notifier.send_reports(config, data_dir)

    job = make_fetch_and_send_job(config, data_dir, fetch_job, send_job)
    run_scheduled_loop(job, interval_hours=hours, run_immediately=not no_immediate)


@telegram.command("bot")
@click.option("--all-qa", is_flag=True, help="Include full-time QA roles when scanning")
@click.option("--automated", is_flag=True, help="Apply automation config (scanning_on_boot, run_on_boot)")
@click.pass_context
def telegram_bot(ctx: click.Context, all_qa: bool, automated: bool) -> None:
    """Run interactive Telegram bot (start/stop scanning via chat commands)."""
    from src.notifications.telegram import TelegramNotifier
    from src.notifications.telegram_bot import TelegramBotController

    config = ctx.obj["config"]
    data_dir = ctx.obj["data_dir"]
    notifier = TelegramNotifier(config)

    if not notifier.is_configured:
        console.print(
            "[red]Telegram not configured.[/red]\n"
            "Set bot_token and chat_id in config.yaml or .env"
        )
        raise SystemExit(1)

    def fetch_job() -> None:
        _run_fetch(ctx, all_qa=all_qa)

    def send_job() -> bool:
        return notifier.send_reports(config, data_dir)

    controller = TelegramBotController(config, data_dir, fetch_job, send_job)
    automation = config.get("automation", {}) if automated else {}
    controller.run(
        auto_start_scanning=automation.get("scanning_on_boot", False),
        run_on_boot=automation.get("run_on_boot", False),
    )


@cli.group()
@click.pass_context
def automate(ctx: click.Context) -> None:
    """Fully automated background operation (bot + scanning + reports)."""
    pass


@automate.command("start")
@click.option("--all-qa", is_flag=True, help="Include full-time QA roles when scanning")
@click.option("--config", "-c", default="config.yaml", hidden=True)
@click.pass_context
def automate_start(ctx: click.Context, all_qa: bool, config: str) -> None:
    """Start automation daemon in background (bot + auto scanning)."""
    from src.automation.daemon import start_daemon

    start_daemon(PROJECT_ROOT, config, all_qa=all_qa)


@automate.command("stop")
@click.pass_context
def automate_stop(ctx: click.Context) -> None:
    """Stop the automation daemon."""
    from src.automation.daemon import stop_daemon

    stop_daemon(ctx.obj["config"], ctx.obj["data_dir"])


@automate.command("status")
@click.pass_context
def automate_status(ctx: click.Context) -> None:
    """Show automation daemon and scanning status."""
    from src.automation.daemon import daemon_status

    status = daemon_status(ctx.obj["config"], ctx.obj["data_dir"])
    running = "running" if status["running"] else "stopped"
    console.print(f"Daemon: {running}")
    if status["pid"]:
        console.print(f"  PID: {status['pid']}")
    console.print(f"  Scanning: {'ON' if status['scanning_enabled'] else 'OFF'}")
    console.print(f"  PID file: {status['pid_file']}")
    console.print(f"  Log file: {status['log_file']}")


@automate.command("restart")
@click.option("--all-qa", is_flag=True, help="Include full-time QA roles when scanning")
@click.pass_context
def automate_restart(ctx: click.Context, all_qa: bool) -> None:
    """Restart the automation daemon."""
    from src.automation.daemon import start_daemon, stop_daemon

    stop_daemon(ctx.obj["config"], ctx.obj["data_dir"])
    start_daemon(PROJECT_ROOT, "config.yaml", all_qa=all_qa)


@automate.command("worker")
@click.option("--all-qa", is_flag=True, help="Include full-time QA roles when scanning")
@click.pass_context
def automate_worker(ctx: click.Context, all_qa: bool) -> None:
    """Internal worker process — runs Telegram bot with automation settings."""
    ctx.invoke(telegram_bot, all_qa=all_qa, automated=True)


if __name__ == "__main__":
    cli()
