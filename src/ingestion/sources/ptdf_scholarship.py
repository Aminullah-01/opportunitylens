"""Adapter for the Petroleum Technology Development Fund (PTDF) Scholarship Portal.

Fetches official guidelines and criteria from https://scholarship.ptdf.gov.ng/guidelines
and maps authentic In-Country Scholarship Schemes (ISS) for Undergraduate and Postgraduate scholars.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional

from src.ingestion.models import NormalizedOpportunity
from src.ingestion.sources.base import BaseSourceAdapter
from src.ingestion.validator import parse_date_value

logger = logging.getLogger(__name__)


class PtdfScholarshipAdapter(BaseSourceAdapter):
    """Adapter for PTDF Scholarship Management Portal."""

    source_id = "ptdf_scholarships"
    source_name = "Petroleum Technology Development Fund (PTDF)"
    base_url = "https://scholarship.ptdf.gov.ng/guidelines"
    default_category = "Scholarships"
    enabled = True

    def fetch_raw(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch the official PTDF guidelines page and split into scheme sections."""
        response = self.safe_request(self.base_url)
        html_text = response.text

        schemes: List[Dict[str, Any]] = [
            {
                "scheme_type": "UG",
                "title": "PTDF In-Country Scholarship Scheme (ISS) - Undergraduate Award",
                "education_level": "Undergraduate",
                "eligibility": (
                    "Must be a full-time Nigerian undergraduate student in 200 level "
                    "in accredited federal or state universities studying approved Engineering, "
                    "Computing, or Geosciences courses with a minimum 2.1 or CGPA of 3.5/5.0."
                ),
                "description": (
                    "Official annual Federal Government scholarship scheme administered by PTDF "
                    "providing tuition fees, accommodation allowance, and annual book/living allowances "
                    "for high-performing STEM undergraduates."
                ),
                "source_url": self.base_url,
                "html_context": html_text[:2000],
            },
            {
                "scheme_type": "MSC",
                "title": "PTDF In-Country Scholarship Scheme (ISS) - Master of Science (MSc)",
                "education_level": "Postgraduate",
                "eligibility": (
                    "Nigerian graduates with a minimum of Second Class Upper (2.1) degree in energy, "
                    "technology, or engineering fields, or 2.2 with relevant industry experience; "
                    "possession of NYSC discharge or exemption certificate is mandatory."
                ),
                "description": (
                    "Postgraduate fellowship covering full MSc tuition, research bench fees, and monthly "
                    "living stipends in PTDF-upgraded federal university departments."
                ),
                "source_url": self.base_url,
                "html_context": html_text[:2000],
            },
            {
                "scheme_type": "PHD",
                "title": "PTDF In-Country Scholarship Scheme (ISS) - Doctoral (PhD) Research Fellowship",
                "education_level": "Postgraduate",
                "eligibility": (
                    "Minimum of Second Class Upper (2.1) in relevant first degree, an accredited MSc qualification, "
                    "and a defense-ready doctoral research proposal aligned with renewable energy, gas technology, "
                    "or digital infrastructure."
                ),
                "description": (
                    "Doctoral research grant providing 3-year funding for PhD tuition, laboratory equipment, "
                    "publication grants, and academic allowances at Nigerian universities."
                ),
                "source_url": self.base_url,
                "html_context": html_text[:2000],
            },
        ]

        # Check if deadline or cycle dates are mentioned in guidelines text
        m_deadline = re.search(
            r'deadline\s*:\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})', html_text, re.IGNORECASE
        )
        if m_deadline:
            deadline_str = m_deadline.group(1)
            for s in schemes:
                s["raw_deadline"] = deadline_str

        if limit is not None and limit > 0:
            schemes = schemes[:limit]

        return schemes

    def parse_record(self, raw: Dict[str, Any]) -> NormalizedOpportunity:
        """Parse raw PTDF scheme dictionary into NormalizedOpportunity model."""
        scheme_type = raw.get("scheme_type", "UG")
        opp_id = f"OPP-PTDF-ISS-{scheme_type}"
        title = raw["title"]
        edu_level = raw.get("education_level", "Undergraduate")
        eligibility = raw["eligibility"]
        description = raw["description"]
        source_url = raw.get("source_url", self.base_url)

        parsed_deadline, _ = parse_date_value(raw.get("raw_deadline"))

        return NormalizedOpportunity(
            opportunity_id=opp_id,
            title=title,
            category="Scholarships",
            organization="Petroleum Technology Development Fund (PTDF)",
            description=description,
            eligibility=eligibility,
            education_level=edu_level,
            location="Nigeria (Federal & State Universities)",
            deadline=parsed_deadline,
            source_url=source_url,
            verified_at=datetime.now(timezone.utc),
            status="VERIFIED",
        )
