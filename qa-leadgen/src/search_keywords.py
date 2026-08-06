"""QA search keyword loading and pattern building."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

KEYWORDS_FILE = Path(__file__).parent.parent / "config" / "qa_search_keywords.yaml"


def _load_yaml_keywords() -> list[str]:
    if not KEYWORDS_FILE.exists():
        return []
    with open(KEYWORDS_FILE, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    terms: list[str] = []
    for section in (
        "titles_roles",
        "automation",
        "specialized_testing",
        "tool_names",
        "search_boosters",
    ):
        for term in raw.get(section, []) or []:
            cleaned = str(term).strip()
            if cleaned and cleaned.lower() not in {t.lower() for t in terms}:
                terms.append(cleaned)
    return terms


def get_search_keywords(config: dict | None = None) -> list[str]:
    """Return merged default + config search keywords (deduplicated, case-insensitive)."""
    config = config or {}
    search = config.get("search", {})
    use_defaults = search.get("use_default_keywords", True)

    terms: list[str] = _load_yaml_keywords() if use_defaults else []
    seen = {t.lower() for t in terms}

    for term in search.get("keywords", []) or []:
        cleaned = str(term).strip()
        if cleaned and cleaned.lower() not in seen:
            terms.append(cleaned)
            seen.add(cleaned.lower())

    return terms


def _term_to_regex(term: str) -> str:
    """Convert a keyword phrase into a word-boundary-safe regex fragment."""
    parts = re.split(r"\s+", term.strip())
    if len(parts) == 1:
        word = re.escape(parts[0])
        if word.lower() in {"qa", "qc", "uat", "sdet"}:
            return rf"\b{word}\b"
        return rf"\b{word}\b"
    inner = r"[\s\-]+".join(re.escape(p) for p in parts)
    return rf"\b{inner}\b"


@lru_cache(maxsize=4)
def _compile_title_pattern(frozen_terms: tuple[str, ...]) -> re.Pattern:
    ordered = sorted(frozen_terms, key=len, reverse=True)
    fragments = [_term_to_regex(t) for t in ordered]
    return re.compile("|".join(fragments), re.IGNORECASE)


DESCRIPTION_EXTRA = re.compile(
    r"\b(qa team|manual testing|test automation|quality assurance|software test|"
    r"test cases|test plan|regression test|automation framework)\b",
    re.IGNORECASE,
)


def get_qa_title_pattern(config: dict | None = None) -> re.Pattern:
    return _compile_title_pattern(tuple(get_search_keywords(config)))


def is_qa_related(title: str, description: str = "", config: dict | None = None) -> bool:
    """Match QA/testing titles using the full keyword list."""
    if get_qa_title_pattern(config).search(title):
        return True

    title_hint = re.search(
        r"\b(test|quality|qa|qc|uat|selenium|playwright|cypress|appium)\b",
        title,
        re.IGNORECASE,
    )
    if not title_hint:
        return False

    if DESCRIPTION_EXTRA.search(description):
        return True

    for term in get_search_keywords(config):
        if _term_in_text(term, description):
            return True

    return False


def _term_in_text(term: str, text: str) -> bool:
    if not text:
        return False
    pattern = re.compile(_term_to_regex(term), re.IGNORECASE)
    return bool(pattern.search(text))


def keyword_matches_text(text: str, keywords: list[str] | None = None) -> bool:
    """Check if any keyword appears in text (for API source filtering)."""
    if not text:
        return False
    lowered = text.lower()
    for term in keywords or []:
        if term.lower() in lowered:
            return True
    return False
