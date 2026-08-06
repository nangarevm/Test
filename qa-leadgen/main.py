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
    load_company_directory,
    load_jobs_tracker,
    merge_jobs,
)
from src.outreach.tracker import OutreachManager

console = Console()


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
    config = ctx.obj["config"]
    if all_qa:
        config.setdefault("search", {})["only_freelance"] = False
    data_dir = ctx.obj["data_dir"]
    jobs_file = data_dir / config["output"]["jobs_tracker"]

    console.print("[bold]Starting job aggregation...[/bold]")
    new_jobs = aggregate_jobs(config)

    existing = load_jobs_tracker(jobs_file) if jobs_file.exists() else []
    merged = merge_jobs(existing, new_jobs)
    export_jobs_tracker(merged, jobs_file)

    freelance = sum(1 for j in merged if j.employment_type in {"Freelance", "Contract", "Part-time"})
    console.print(f"[green]Saved {len(merged)} jobs to {jobs_file}[/green]")
    if merged:
        console.print(f"  Employment breakdown: {freelance} freelance/contract/part-time, {len(merged) - freelance} other")
        for j in merged[:10]:
            console.print(f"    [{j.employment_type}] {j.company} — {j.role} ({j.source})")
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


if __name__ == "__main__":
    cli()
