"""Generic RSS and JSON feed adapters for platform registry entries."""

from __future__ import annotations

import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Iterable
from xml.etree import ElementTree

from src.aggregator.base import JobSource, extract_email
from src.aggregator.platforms_registry import Platform
from src.models import JobPosting


class RSSPlatformSource(JobSource):
    """Fetch jobs from any RSS/Atom feed defined in the platform registry."""

    def __init__(self, config: dict, platform: Platform, session=None) -> None:
        super().__init__(config, session)
        self.platform = platform
        self.name = platform.name

    def fetch(self, keywords: Iterable[str]) -> list[JobPosting]:
        if not self.platform.feed_url:
            return []
        jobs: list[JobPosting] = []
        resp = self._get(self.platform.feed_url)
        jobs.extend(self._parse_feed(resp.text, keywords))
        return jobs

    def _parse_feed(self, xml_text: str, keywords: Iterable[str]) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        keyword_set = {k.lower() for k in keywords}
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            return jobs

        items = root.findall(".//item") or root.findall(".//{*}entry")
        for item in items:
            title = self._text(item, "title")
            link = self._text(item, "link") or item.findtext("{*}link")
            if not link:
                link_el = item.find("{*}link")
                if link_el is not None:
                    link = link_el.get("href", "")
            description = (
                self._text(item, "description")
                or self._text(item, "summary")
                or self._text(item, "content")
            )
            pub_date = self._text(item, "pubDate") or self._text(item, "published")

            company, role = self._split_title(title)
            searchable = f"{title} {description}".lower()
            if keyword_set and not any(k in searchable for k in keyword_set):
                continue

            date_found = self._parse_date(pub_date)
            posting = self._make_posting(
                company=company,
                role=role,
                jd_text=self._strip_html(description),
                location="Remote",
                source=self.name,
                posting_link=link,
                contact_email=extract_email(description),
                date_found=date_found,
            )
            if posting:
                jobs.append(posting)
        return jobs

    @staticmethod
    def _text(item: ElementTree.Element, tag: str) -> str:
        el = item.find(tag) or item.find(f"{{*}}{tag}")
        return (el.text or "").strip() if el is not None else ""

    @staticmethod
    def _split_title(title: str) -> tuple[str, str]:
        for sep in (":", " at ", " - ", " — "):
            if sep in title:
                left, right = title.split(sep, 1)
                if len(left) < 60:
                    return left.strip(), right.strip()
        return "Unknown", title.strip()

    @staticmethod
    def _strip_html(text: str) -> str:
        return re.sub(r"<[^>]+>", " ", text or "")

    @staticmethod
    def _parse_date(pub_date: str) -> datetime:
        if not pub_date:
            return datetime.utcnow()
        try:
            return parsedate_to_datetime(pub_date).replace(tzinfo=None)
        except (ValueError, TypeError):
            try:
                return datetime.fromisoformat(pub_date.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                return datetime.utcnow()


class JSONPlatformSource(JobSource):
    """Fetch jobs from public JSON APIs with configurable field mapping."""

    def __init__(self, config: dict, platform: Platform, session=None) -> None:
        super().__init__(config, session)
        self.platform = platform
        self.name = platform.name
        self.mapping = platform.json_mapping

    def fetch(self, keywords: Iterable[str]) -> list[JobPosting]:
        if not self.platform.feed_url:
            return []
        jobs: list[JobPosting] = []
        resp = self._get(self.platform.feed_url)
        data = resp.json()
        jobs.extend(self._parse_json(data, keywords))
        return jobs

    def _parse_json(self, data: Any, keywords: Iterable[str]) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        keyword_set = {k.lower() for k in keywords}
        items = self._extract_items(data)

        for item in items:
            if not isinstance(item, dict):
                continue
            title = self._field(item, "title")
            company = self._field(item, "company") or "Unknown"
            if company == "Unknown":
                company = self._company_from_url(self._field(item, "link"))
            description = self._field(item, "description") or ""
            link = self._field(item, "link") or self.platform.url
            location = self._field(item, "location") or "Remote"
            api_job_type = self._field(item, "employment_type")

            searchable = f"{title} {description} {company}".lower()
            if keyword_set and not any(k in searchable for k in keyword_set):
                continue

            posting = self._make_posting(
                company=company,
                role=title,
                jd_text=description,
                location=location,
                source=self.name,
                posting_link=link,
                api_job_type=api_job_type,
            )
            if posting:
                jobs.append(posting)
        return jobs

    def _extract_items(self, data: Any) -> list[dict]:
        path = self.mapping.get("items_path", "")
        if not path:
            return data if isinstance(data, list) else []
        current = data
        for key in path.split("."):
            if isinstance(current, dict):
                current = current.get(key, [])
            else:
                return []
        return current if isinstance(current, list) else []

    def _field(self, item: dict, logical_name: str) -> str:
        key = self.mapping.get(logical_name, logical_name)
        value = item.get(key, "")
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        return str(value) if value is not None else ""

    @staticmethod
    def _company_from_url(url: str) -> str:
        if not url:
            return "Unknown"
        parts = url.rstrip("/").split("/")
        for i, part in enumerate(parts):
            if part in ("job", "jobs", "companies") and i + 1 < len(parts):
                slug = parts[i + 1]
                return slug.replace("-", " ").title()
        return "Unknown"


def create_platform_source(config: dict, platform: Platform) -> JobSource | None:
    if platform.adapter == "rss":
        return RSSPlatformSource(config, platform)
    if platform.adapter == "json":
        return JSONPlatformSource(config, platform)
    return None
