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
    export_remote_qa_companies,
    load_company_directory,
    load_jobs_tracker,
    merge_jobs,
)
from src.aggregator.platforms_registry import load_platforms
from src.company_sources import catalog_summary, load_company_catalog, resolve_company_sources
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
    export_remote_qa_companies(resolve_company_sources(config), jobs_file)
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
@click.option("--country", "-C", default=None, help="Filter by country/region (e.g. India)")
@click.option(
    "--region",
    "-R",
    default=None,
    type=click.Choice(["usa", "europe", "australia", "uae"]),
    help="Filter by target market region",
)
@click.option("--fetchable-only", is_flag=True, help="Show only platforms with automated feeds")
@click.option("--summary", is_flag=True, help="Show country coverage summary only")
@click.pass_context
def platforms_cmd(
    ctx: click.Context,
    category: str | None,
    country: str | None,
    region: str | None,
    fetchable_only: bool,
    summary: bool,
) -> None:
    """List registered job platforms and country coverage."""
    from rich.table import Table

    from src.aggregator.platforms_registry import (
        category_label,
        country_coverage_summary,
        group_platforms,
        load_platforms,
        resolve_enabled_platforms,
    )
    from src.regions import REGION_LABELS, platform_regions, region_portal_summary

    config = ctx.obj["config"]
    all_platforms = load_platforms()
    enabled = {p.id for p in resolve_enabled_platforms(config)}
    coverage = country_coverage_summary(all_platforms)

    if summary:
        table = Table(title="Job Portal Country Coverage")
        table.add_column("Country/Region")
        table.add_column("Portals", justify="right")
        for country_name, count in coverage["by_country"].items():
            table.add_row(country_name, str(count))
        console.print(table)

        region_table = Table(title="USA / Europe / Australia / UAE Coverage")
        region_table.add_column("Region")
        region_table.add_column("Portals", justify="right")
        region_table.add_column("Auto-fetch", justify="right")
        for label, stats in region_portal_summary(all_platforms).items():
            region_table.add_row(label, str(stats["total"]), str(stats["fetchable"]))
        console.print(region_table)

        console.print(
            f"\nTotal portals: {coverage['total_portals']} "
            f"({coverage['fetchable_portals']} auto-fetch, {coverage['manual_portals']} manual) | "
            f"Global boards: {coverage['global_portals']} | "
            f"Countries/regions: {coverage['countries_regions']}"
        )
        return

    filtered = all_platforms
    if category:
        filtered = [p for p in filtered if p.category == category]
    if region:
        filtered = [
            p for p in filtered
            if region in platform_regions(p.country or "Global")
        ]
    if country:
        needle = country.lower()
        filtered = [
            p for p in filtered
            if needle in (p.country or "Global").lower() or needle == "global" and not p.country
        ]

    if category:
        groups = {category: filtered}
    else:
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
                p.country or "Global",
                p.url,
            )
    console.print(table)
    console.print(
        f"\n{coverage['fetchable_portals']} platforms have automated adapters; "
        f"{len(enabled)} enabled in current config."
    )
    console.print(
        f"Coverage: {coverage['total_portals']} portals across "
        f"{coverage['countries_regions']} countries/regions + "
        f"{coverage['global_portals']} global boards."
    )


@cli.command("companies")
@click.option("--summary", is_flag=True, help="Show catalog summary only")
@click.option("--ats-only", is_flag=True, help="Show only ATS auto-fetch companies")
@click.option("--limit", default=25, help="Rows to display (default 25)")
@click.pass_context
def companies_cmd(ctx: click.Context, summary: bool, ats_only: bool, limit: int) -> None:
    """List 500 remote QA employers paying USD globally."""
    from rich.table import Table

    config = ctx.obj["config"]
    companies = resolve_company_sources(config)
    stats = catalog_summary(companies)

    if summary:
        console.print("[bold]Remote QA Company Catalog (USD, global)[/bold]")
        console.print(f"  Total companies: {stats['total']}")
        console.print(f"  Remote: {stats['remote']} | Pays USD: {stats['pays_usd']}")
        console.print(f"  ATS auto-fetch: {stats['ats_fetchable']}")
        console.print(f"  Catalog/reference only: {stats['website_only']}")
        console.print(f"  By ATS: {stats['by_ats']}")
        console.print("\nSheet in Excel: Remote QA Companies (USD)")
        return

    if ats_only:
        companies = [c for c in companies if c.is_ats_fetchable]

    table = Table(title=f"Remote QA Companies ({len(companies)} shown)")
    table.add_column("Company")
    table.add_column("ATS")
    table.add_column("Region")
    table.add_column("Careers URL", overflow="fold")

    for company in companies[:limit]:
        table.add_row(
            company.name,
            company.ats,
            company.region,
            company.careers_url,
        )
    console.print(table)
    if len(companies) > limit:
        console.print(f"\nShowing {limit} of {len(companies)}. Use --limit to see more.")
    console.print(
        f"\nCatalog: {stats['total']} companies | "
        f"{stats['ats_fetchable']} scanned via ATS APIs each fetch run"
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
