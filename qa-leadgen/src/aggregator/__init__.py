"""Job aggregator orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console

from src.aggregator.arbeitnow import ArbeitnowSource
from src.aggregator.custom_careers import CustomCareerPageSource
from src.aggregator.deduplicator import deduplicate_jobs
from src.aggregator.indeed import IndeedSource
from src.aggregator.linkedin_jobs import LinkedInJobsSource
from src.aggregator.remotive import RemotiveSource
from src.aggregator.remoteok import RemoteOKSource
from src.aggregator.upwork import UpworkSource
from src.aggregator.wellfound import WellfoundSource
from src.aggregator.weworkremotely import WeWorkRemotelySource
from src.models import JobPosting

if TYPE_CHECKING:
    pass

console = Console()

SOURCE_REGISTRY = {
    "remoteok": RemoteOKSource,
    "weworkremotely": WeWorkRemotelySource,
    "remotive": RemotiveSource,
    "arbeitnow": ArbeitnowSource,
    "indeed": IndeedSource,
    "upwork": UpworkSource,
    "wellfound": WellfoundSource,
    "linkedin_jobs": LinkedInJobsSource,
    "custom_career_pages": CustomCareerPageSource,
}


def aggregate_jobs(config: dict) -> list[JobPosting]:
    keywords = config.get("search", {}).get("keywords", ["QA"])
    sources_config = config.get("sources", {})
    all_jobs: list[JobPosting] = []

    for source_key, enabled in sources_config.items():
        if source_key == "custom_career_pages":
            if not sources_config.get("custom_career_pages"):
                continue
            enabled = True
        if not enabled:
            continue

        source_cls = SOURCE_REGISTRY.get(source_key)
        if not source_cls:
            continue

        source = source_cls(config)
        console.print(f"[cyan]Fetching from {source.name}...[/cyan]")
        try:
            jobs = source.fetch(keywords)
            console.print(f"  Found {len(jobs)} QA postings")
            all_jobs.extend(jobs)
        except Exception as exc:
            console.print(f"  [yellow]Warning: {source.name} failed: {exc}[/yellow]")

    deduped = deduplicate_jobs(all_jobs)

    freelance_count = sum(
        1 for j in deduped if j.employment_type in {"Freelance", "Contract", "Part-time"}
    )
    console.print(f"[green]Total unique QA postings: {len(deduped)}[/green]")
    if deduped:
        console.print(
            f"  Freelance/contract/part-time: {freelance_count} | "
            f"Other: {len(deduped) - freelance_count}"
        )
    elif config.get("search", {}).get("only_freelance"):
        console.print(
            "[yellow]No freelance/contract QA postings found. "
            "Try: set search.only_freelance to false, enable Upwork/Indeed APIs, "
            "or add custom career pages.[/yellow]"
        )
    return deduped
