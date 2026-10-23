"""Unit tests for natural-language query parser and search filtering."""

from __future__ import annotations

import pytest

from src.matching.models import SearchRequest
from src.matching.search import filter_by_search_request, parse_natural_language_query


def test_parse_query_category_intent():
    """Verify that user queries with category keywords extract canonical categories."""
    # Scholarships
    req_sch = parse_natural_language_query("Find scholarships for a computer science undergraduate")
    assert "Scholarships" in req_sch.categories

    # Internships & Delivery mode
    req_intern = parse_natural_language_query("Show remote internships suitable for students")
    assert "Internships" in req_intern.categories
    assert req_intern.delivery_mode == "remote"

    # Tech Training
    req_train = parse_natural_language_query("Looking for developer bootcamps and training programs")
    assert "Tech Training" in req_train.categories

    # Hackathons
    req_hack = parse_natural_language_query("Are there any upcoming hackathons or coding challenges?")
    assert "Hackathons" in req_hack.categories

    # Entry-level jobs
    req_job = parse_natural_language_query("Entry-level jobs and graduate trainee positions")
    assert "Entry-Level Jobs" in req_job.categories


def test_parse_query_education_intent():
    """Verify extraction of target education standing."""
    req_undergrad = parse_natural_language_query("Undergraduate research opportunities")
    assert req_undergrad.education_level == "Undergraduate"

    req_postgrad = parse_natural_language_query("Masters and PhD fellowships")
    assert req_postgrad.education_level == "Postgraduate"


def test_parse_query_location_intent():
    """Verify extraction of Nigerian cities and states."""
    req_gombe = parse_natural_language_query("Tech opportunities in Gombe state")
    assert req_gombe.location == "Gombe"

    req_lagos = parse_natural_language_query("Find developer internships in Lagos")
    assert req_lagos.location == "Lagos"


def test_parse_query_deadline_urgency():
    """Verify detection of closing soon urgency."""
    req_urgent = parse_natural_language_query("Which opportunities have deadlines coming soon?")
    assert req_urgent.closing_soon_only is True

    req_normal = parse_natural_language_query("All available scholarships")
    assert req_normal.closing_soon_only is False


def test_parse_empty_query():
    """Verify empty or whitespace queries return clean empty SearchRequest."""
    req_empty = parse_natural_language_query("")
    assert req_empty.query_text == ""
    assert len(req_empty.categories) == 0
    assert len(req_empty.keywords) == 0

    req_whitespace = parse_natural_language_query("   ")
    assert req_whitespace.query_text == ""


def test_filter_by_search_request():
    """Verify opportunity filtering against structured SearchRequest."""
    opportunities = [
        {
            "opportunity_id": "opp-1",
            "title": "Gombe State Undergraduate Scholarship",
            "category": "Scholarships",
            "education_level": "Undergraduate",
            "location": "Gombe",
            "status": "Open",
            "description": "Scholarship for Gombe students.",
        },
        {
            "opportunity_id": "opp-2",
            "title": "Remote Python Internship",
            "category": "Internships",
            "education_level": "Undergraduate",
            "location": "Remote",
            "status": "Closing Soon",
            "description": "Remote software engineering internship with Python.",
        },
        {
            "opportunity_id": "opp-3",
            "title": "Lagos Tech Bootcamp",
            "category": "Tech Training",
            "education_level": "All Levels",
            "location": "Lagos",
            "status": "Open",
            "description": "Intensive web development bootcamp.",
        },
    ]

    # Filter by category: Scholarships
    req_cat = SearchRequest(categories=["Scholarships"])
    res_cat = filter_by_search_request(opportunities, req_cat)
    assert len(res_cat) == 1
    assert res_cat[0]["opportunity_id"] == "opp-1"

    # Filter by keyword: Python
    req_kw = SearchRequest(keywords=["python"])
    res_kw = filter_by_search_request(opportunities, req_kw)
    assert len(res_kw) == 1
    assert res_kw[0]["opportunity_id"] == "opp-2"

    # Filter by closing soon
    req_soon = SearchRequest(closing_soon_only=True)
    res_soon = filter_by_search_request(opportunities, req_soon)
    assert len(res_soon) == 3  # All 3 are Open or Closing Soon
