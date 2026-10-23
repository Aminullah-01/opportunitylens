"""Demo dataset and data-access helpers for OpportunityLens.

This module provides fictional sample data for interface development prior to
connecting to live Snowflake tables. All records are explicitly flagged as sample
records and should never be treated as real, verified opportunities.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Canonical categories supported by OpportunityLens
VALID_CATEGORIES = (
    "Scholarships",
    "Internships",
    "Tech Training",
    "Hackathons",
    "Entry-Level Jobs",
)

# Canonical status values
VALID_STATUSES = (
    "Open",
    "Closing Soon",
    "Closed",
)

# Small, clearly labelled set of fictional example records
# Designed to mirror the target Snowflake schema in Phase 2
DEMO_OPPORTUNITIES: List[Dict[str, Any]] = [
    {
        "opportunity_id": "DEMO-SCH-001",
        "title": "Northern Nigeria Women in STEM Undergraduate Scholarship",
        "category": "Scholarships",
        "organization": "Arewa Tech Horizons Trust",
        "description": "Fictional annual grant providing tuition support, laptop subsidies, and mentorship for female undergraduates enrolled in computer science or engineering at accredited Nigerian universities.",
        "eligibility": "Female undergraduate students in 200L/300L studying STEM fields in Northern Nigerian institutions; minimum CGPA of 3.5/5.0.",
        "education_level": "Undergraduate",
        "location": "Gombe / Northern Nigeria (Hybrid)",
        "deadline": "2026-11-30",
        "source_url": "https://example.org/fictional-stem-scholarship",
        "verified_at": "2026-10-15T10:00:00Z",
        "status": "Open",
        "is_sample_data": True,
    },
    {
        "opportunity_id": "DEMO-INT-002",
        "title": "FinTech Cloud Infrastructure Engineering Internship",
        "category": "Internships",
        "organization": "NaijaPay Solutions Ltd",
        "description": "Fictional 6-month paid internship program offering hands-on training with distributed systems, database scaling, and cloud automation.",
        "eligibility": "Pre-final or final-year students, or recent graduates with foundational knowledge of Python, Linux, and SQL.",
        "education_level": "Undergraduate / Recent Graduate",
        "location": "Lagos, Nigeria (Hybrid)",
        "deadline": "2026-11-15",
        "source_url": "https://example.org/fictional-fintech-internship",
        "verified_at": "2026-10-12T14:30:00Z",
        "status": "Closing Soon",
        "is_sample_data": True,
    },
    {
        "opportunity_id": "DEMO-TRN-003",
        "title": "National Applied AI & Data Engineering Bootcamp",
        "category": "Tech Training",
        "organization": "Apex Digital Skills Initiative",
        "description": "Fictional 12-week virtual intensive bootcamp teaching data warehousing, SQL query optimization, and open-weight LLM deployment for Nigerian developers.",
        "eligibility": "Open to all Nigerian youths with basic coding familiarity; requires a PC and commitment of 15 hours per week.",
        "education_level": "All Levels",
        "location": "Remote / Nationwide",
        "deadline": "2026-12-05",
        "source_url": "https://example.org/fictional-ai-bootcamp",
        "verified_at": "2026-10-18T09:15:00Z",
        "status": "Open",
        "is_sample_data": True,
    },
    {
        "opportunity_id": "DEMO-HCK-004",
        "title": "Gombe Innovation Hackathon: AI for Agriculture & Health",
        "category": "Hackathons",
        "organization": "Gombe State Technology Hub",
        "description": "Fictional 48-hour collaborative hackathon challenging university teams to build open-source AI solutions addressing local agricultural supply chain and public health logistics.",
        "eligibility": "Teams of 2 to 4 students from tertiary institutions across Nigeria.",
        "education_level": "Tertiary Students",
        "location": "Gombe, Nigeria (In-Person)",
        "deadline": "2026-11-10",
        "source_url": "https://example.org/fictional-gombe-hackathon",
        "verified_at": "2026-10-14T11:45:00Z",
        "status": "Closing Soon",
        "is_sample_data": True,
    },
    {
        "opportunity_id": "DEMO-JOB-005",
        "title": "Junior Python & Data Pipeline Associate",
        "category": "Entry-Level Jobs",
        "organization": "Kwara Analytics Lab",
        "description": "Fictional full-time entry-level role assisting with ETL pipeline construction, data cleaning, and dashboard development using Streamlit and SQL.",
        "eligibility": "Graduates with 0-1 year of professional experience, demonstrated GitHub portfolio in Python/Pandas, and completion of NYSC.",
        "education_level": "BSc / HND Graduate",
        "location": "Ilorin / Remote",
        "deadline": "2026-12-15",
        "source_url": "https://example.org/fictional-junior-pipeline-associate",
        "verified_at": "2026-10-16T16:00:00Z",
        "status": "Open",
        "is_sample_data": True,
    },
    {
        "opportunity_id": "DEMO-SCH-006",
        "title": "Future Tech Leaders Postgraduate Fellowship",
        "category": "Scholarships",
        "organization": "Continental Education Foundation",
        "description": "Fictional full-tuition scholarship and living stipend for exceptional Nigerian scholars pursuing Master's degrees in Artificial Intelligence or Data Science.",
        "eligibility": "First-class or strong Second-class upper degree holders accepted into accredited MSc programs.",
        "education_level": "Postgraduate",
        "location": "Nationwide / Global Study",
        "deadline": "2026-10-01",
        "source_url": "https://example.org/fictional-postgraduate-fellowship",
        "verified_at": "2026-09-20T08:00:00Z",
        "status": "Closed",
        "is_sample_data": True,
    },
]


def get_demo_opportunities() -> List[Dict[str, Any]]:
    """Return a deep copy of demo opportunities to prevent accidental mutation."""
    return [dict(record) for record in DEMO_OPPORTUNITIES]


def get_categories() -> List[str]:
    """Return the list of standard opportunity categories."""
    return list(VALID_CATEGORIES)


def filter_opportunities(
    opportunities: List[Dict[str, Any]],
    query: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    education_level: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Filter opportunity records by search keyword, category, status, location, and education level.

    Pure function designed to be easily testable outside of Streamlit UI.

    Args:
        opportunities: List of opportunity dictionaries.
        query: Optional free-text search string matched against title,
            organization, description, and location.
        category: Optional category filter. If 'All' or empty, category filter is skipped.
        status: Optional status filter. If 'All' or empty, status filter is skipped.
        location: Optional location filter. If 'All' or empty, location filter is skipped.
        education_level: Optional education level filter. If 'All' or empty, filter is skipped.

    Returns:
        Filtered list of opportunity dictionaries.
    """
    filtered = opportunities

    # Filter by category
    if category and category != "All":
        filtered = [opp for opp in filtered if opp.get("category") == category]

    # Filter by status
    if status and status != "All":
        filtered = [opp for opp in filtered if opp.get("status") == status]

    # Filter by location
    if location and location != "All":
        loc_target = location.strip().lower()
        filtered = [
            opp
            for opp in filtered
            if loc_target in (opp.get("location") or "").lower()
        ]

    # Filter by education level
    if education_level and education_level != "All":
        edu_target = education_level.strip().lower()
        filtered = [
            opp
            for opp in filtered
            if edu_target in (opp.get("education_level") or "").lower()
        ]

    # Filter by search query
    if query and query.strip():
        q = query.strip().lower()
        filtered = [
            opp
            for opp in filtered
            if q in (opp.get("title") or "").lower()
            or q in (opp.get("organization") or "").lower()
            or q in (opp.get("description") or "").lower()
            or q in (opp.get("location") or "").lower()
            or q in (opp.get("eligibility") or "").lower()
        ]

    return filtered


def get_demo_metrics(opportunities: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Calculate aggregate counts for dashboard metric cards.

    Args:
        opportunities: Optional list of opportunity records. If None, uses demo data.

    Returns:
        Dictionary containing aggregate counts with preview labels.
    """
    records = opportunities if opportunities is not None else get_demo_opportunities()

    total = len(records)
    scholarships = sum(1 for r in records if r.get("category") == "Scholarships")
    internships = sum(1 for r in records if r.get("category") == "Internships")
    training = sum(1 for r in records if r.get("category") == "Tech Training")
    hackathons = sum(1 for r in records if r.get("category") == "Hackathons")
    jobs = sum(1 for r in records if r.get("category") == "Entry-Level Jobs")

    return {
        "total": total,
        "scholarships": scholarships,
        "internships": internships,
        "training": training,
        "hackathons": hackathons,
        "jobs": jobs,
        "is_preview": True,
        "data_source": "Fictional Demo Dataset (Snowflake Disconnected)",
    }
