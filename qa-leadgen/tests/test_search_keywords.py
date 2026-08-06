"""Tests for QA search keyword loading and matching."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.search_keywords import get_search_keywords, is_qa_related, keyword_matches_text


def test_get_search_keywords_includes_user_terms():
    keywords = get_search_keywords()
    lowered = {k.lower() for k in keywords}
    expected = {
        "qa engineer",
        "quality assurance engineer",
        "sdet",
        "test automation engineer",
        "manual tester",
        "performance tester",
        "game qa",
        "user acceptance test",
        "selenium",
        "playwright",
        "cypress",
        "appium",
        "qa consultant",
        "automation qa",
    }
    assert expected.issubset(lowered)
    assert len(keywords) >= 43


def test_is_qa_related_title_matches():
    assert is_qa_related("QA Consultant", "")
    assert is_qa_related("Playwright Engineer", "build test suites")
    assert is_qa_related("Cypress Developer", "")
    assert is_qa_related("Manual QA Specialist", "")
    assert is_qa_related("Game Tester", "PC and console titles")
    assert is_qa_related("UAT Analyst", "")
    assert is_qa_related("Performance Tester", "")


def test_is_qa_related_rejects_unrelated():
    assert not is_qa_related("Senior Java Backend Developer", "Spring Boot microservices")
    assert not is_qa_related("Avi Go", "quality assurance math ops golang")


def test_keyword_matches_text():
    keywords = get_search_keywords()
    assert keyword_matches_text("Hiring a test automation engineer", keywords)
    assert not keyword_matches_text("Senior Java Backend Developer", keywords)
