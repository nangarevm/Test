"""Job aggregator orchestrator."""

from __future__ import annotations

from rich.console import Console

from src.aggregator.arbeitnow import ArbeitnowSource
from src.aggregator.custom_careers import CustomCareerPageSource
from src.aggregator.deduplicator import deduplicate_jobs
from src.aggregator.feed_adapters import create_platform_source
from src.aggregator.indeed import IndeedSource
from src.aggregator.linkedin_jobs import LinkedInJobsSource
from src.aggregator.platforms_registry import Platform, resolve_enabled_platforms
from src.aggregator.remotive import RemotiveSource
from src.aggregator.remoteok import RemoteOKSource
from src.aggregator.upwork import UpworkSource
from src.aggregator.wellfound import WellfoundSource
from src.aggregator.weworkremotely import WeWorkRemotelySource
from src.models import JobPosting
from src.regions import filter_jobs_by_regions, platform_regions
from src.search_keywords import get_search_keywords

console = Console()

BUILTIN_REGISTRY = {
    "remoteok": RemoteOKSource,
    "weworkremotely": WeWorkRemotelySource,
    "remotive": RemotiveSource,
    "arbeitnow": ArbeitnowSource,
    "indeed": IndeedSource,
    "upwork": UpworkSource,
    "wellfound": WellfoundSource,
    "linkedin_jobs": LinkedInJobsSource,
}

# Backward-compatible alias
SOURCE_REGISTRY = BUILTIN_REGISTRY


def _create_source(config: dict, platform: Platform):
    if platform.adapter == "builtin":
        cls = BUILTIN_REGISTRY.get(platform.builtin_key or platform.id)
        if cls:
            return cls(config)
        return None
    return create_platform_source(config, platform)


def _fetch_custom_careers(config: dict, keywords) -> list[JobPosting]:
    urls = config.get("sources", {}).get("custom_career_pages", [])
    if not urls:
        return []
    source = CustomCareerPageSource(config)
    console.print(f"[cyan]Fetching from {source.name}...[/cyan]")
    try:
        jobs = source.fetch(keywords)
        console.print(f"  Found {len(jobs)} QA postings")
        return jobs
    except Exception as exc:
        console.print(f"  [yellow]Warning: {source.name} failed: {exc}[/yellow]")
        return []


def aggregate_jobs(config: dict) -> list[JobPosting]:
    keywords = get_search_keywords(config)
    search = config.get("search", {})
    target_regions = search.get("regions", [])
    enabled_platforms = resolve_enabled_platforms(config)

    if target_regions:
        enabled_platforms = [
            p for p in enabled_platforms
            if any(region in platform_regions(p.country) for region in target_regions)
        ]

    all_jobs: list[JobPosting] = []

    for platform in enabled_platforms:
        source = _create_source(config, platform)
        if not source:
            continue
        console.print(f"[cyan]Fetching from {source.name}...[/cyan]")
        try:
            jobs = source.fetch(keywords)
            console.print(f"  Found {len(jobs)} QA postings")
            all_jobs.extend(jobs)
        except Exception as exc:
            console.print(f"  [yellow]Warning: {source.name} failed: {exc}[/yellow]")

    all_jobs.extend(_fetch_custom_careers(config, keywords))

    deduped = deduplicate_jobs(all_jobs)
    deduped = filter_jobs_by_regions(deduped, target_regions)

    freelance_count = sum(
        1 for j in deduped if j.employment_type in {"Freelance", "Contract", "Part-time"}
    )
    console.print(f"[green]Total unique QA postings: {len(deduped)}[/green]")
    if deduped:
        console.print(
            f"  Freelance/contract/part-time: {freelance_count} | "
            f"Other: {len(deduped) - freelance_count}"
        )
        if target_regions:
            from src.regions import REGION_LABELS

            labels = [REGION_LABELS[r] for r in target_regions if r in REGION_LABELS]
            console.print(f"  Regions: {', '.join(labels)}")
    elif config.get("search", {}).get("only_freelance"):
        console.print(
            "[yellow]No freelance/contract QA postings found. "
            "Try: python main.py fetch --all-qa, enable Upwork/Indeed APIs, "
            "or add custom career pages.[/yellow]"
        )
    return deduped
