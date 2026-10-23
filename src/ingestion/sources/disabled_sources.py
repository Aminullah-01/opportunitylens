"""Safely disabled source adapters with documented policy, authentication, or interface limitations.

In accordance with OpportunityLens data ethics:
- Does not scrape sites requiring login or third-party authentication (e.g. LinkedIn).
- Does not bypass anti-bot mechanisms, paywalls, or CAPTCHAs.
- Explicitly documents why automated collection is currently withheld.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.ingestion.models import NormalizedOpportunity
from src.ingestion.sources.base import BaseSourceAdapter


class AirtelCareersAdapter(BaseSourceAdapter):
    """Adapter for Airtel Nigeria Careers (Safely Disabled)."""

    source_id = "airtel_careers"
    source_name = "Airtel Nigeria Careers"
    base_url = "https://www.airtel.com.ng/ng/about/careers"
    default_category = "Entry-Level Jobs"
    enabled = False
    disabled_reason = (
        "Airtel Nigeria career portal delegates candidate searches to third-party "
        "LinkedIn job queries, which require authentication, present anti-bot controls, "
        "and prohibit automated scraping in their Terms of Service."
    )

    def fetch_raw(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return []

    def parse_record(self, raw: Dict[str, Any]) -> NormalizedOpportunity:
        raise NotImplementedError("AirtelCareersAdapter is disabled.")


class FederalMinistryEducationAdapter(BaseSourceAdapter):
    """Adapter for Federal Ministry of Education Scholarship Portal (Safely Disabled)."""

    source_id = "fed_min_education"
    source_name = "Federal Ministry of Education Scholarship Portal"
    base_url = "https://scholarship.education.gov.ng/"
    default_category = "Scholarships"
    enabled = False
    disabled_reason = (
        "Federal Ministry of Education scholarship portal currently presents a minimal "
        "landing page (1.8KB) with no open, machine-readable public opportunity catalogue "
        "or active unauthenticated application listings."
    )

    def fetch_raw(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return []

    def parse_record(self, raw: Dict[str, Any]) -> NormalizedOpportunity:
        raise NotImplementedError("FederalMinistryEducationAdapter is disabled.")


class YsiInnovationAdapter(BaseSourceAdapter):
    """Adapter for Youth and Students in Innovation Platform (Safely Disabled)."""

    source_id = "ysi_innovation"
    source_name = "Youth and Students in Innovation (YSI)"
    base_url = "https://ysi.scienceandtech.gov.ng/"
    default_category = "Hackathons"
    enabled = False
    disabled_reason = (
        "YSI Science & Technology portal currently hosts static policy and initiative "
        "overviews without an active, machine-readable public catalogue of hackathons or training programs."
    )

    def fetch_raw(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return []

    def parse_record(self, raw: Dict[str, Any]) -> NormalizedOpportunity:
        raise NotImplementedError("YsiInnovationAdapter is disabled.")
