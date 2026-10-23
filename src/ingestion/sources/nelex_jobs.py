"""Adapter for the National Electronic Labour Exchange (NELEX).

Discovers approved employment listings and capacity building programs from
https://nelex.gov.ng/ under the Federal Ministry of Labour and Employment.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from html import unescape
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from src.ingestion.models import NormalizedOpportunity
from src.ingestion.sources.base import BaseSourceAdapter
from src.ingestion.validator import parse_date_value

logger = logging.getLogger(__name__)


class NelexJobsAdapter(BaseSourceAdapter):
    """Adapter for National Electronic Labour Exchange portal."""

    source_id = "nelex_jobs"
    source_name = "National Electronic Labour Exchange (NELEX)"
    base_url = "https://nelex.gov.ng/"
    default_category = "Entry-Level Jobs"
    enabled = True
    timeout_seconds = 20.0

    def fetch_raw(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch job links from NELEX homepage and retrieve individual job pages."""
        response = self.safe_request(self.base_url)
        html_text = response.text

        # Find job links: /job/<slug>
        detail_paths = re.findall(
            r'href=[\"\'](/job/[a-zA-Z0-9\-_]+)[\"\']', html_text, re.IGNORECASE
        )
        if not detail_paths:
            detail_paths = re.findall(
                r'href=[\"\'](https://nelex\.gov\.ng/job/[a-zA-Z0-9\-_]+)[\"\']',
                html_text,
                re.IGNORECASE,
            )

        unique_urls = []
        seen = set()
        for p in detail_paths:
            full_url = urljoin(self.base_url, p)
            if full_url not in seen:
                seen.add(full_url)
                unique_urls.append(full_url)

        # Also add Employability Training event if found
        event_match = re.search(
            r'href=[\"\'](https://nelex\.gov\.ng/events/[^\"\']+)[\"\']',
            html_text,
            re.IGNORECASE,
        )
        if event_match:
            event_url = event_match.group(1)
            if event_url not in seen:
                unique_urls.append(event_url)

        if limit is not None and limit > 0:
            unique_urls = unique_urls[:limit]

        raw_payloads: List[Dict[str, Any]] = []

        for job_url in unique_urls:
            try:
                detail_resp = self.safe_request(job_url)
                raw_payloads.append({
                    "source_url": job_url,
                    "html": detail_resp.text,
                })
            except Exception as exc:
                logger.warning("Failed to fetch NELEX job page from %s: %s", job_url, exc)
                continue

        return raw_payloads

    def parse_record(self, raw: Dict[str, Any]) -> NormalizedOpportunity:
        """Parse raw NELEX HTML into NormalizedOpportunity."""
        source_url = raw.get("source_url", "")
        html = raw.get("html", "")

        # 1. Title
        title = None
        # Try finding title in heading or title tag
        h_match = re.search(r'<h[1-3][^>]*>(.*?)</h[1-3]>', html, re.DOTALL | re.IGNORECASE)
        if h_match:
            clean_h = re.sub(r'<[^>]+>', '', h_match.group(1)).strip()
            if "NELEX" not in clean_h and len(clean_h) > 3:
                title = clean_h

        if not title:
            # Derive from slug
            slug = source_url.rstrip("/").split("/")[-1]
            title = slug.replace("-", " ").title()

        clean_title = unescape(title).strip()

        # 2. Category
        t_lower = clean_title.lower()
        if "training" in t_lower or "workshop" in t_lower:
            category = "Tech Training"
        elif "intern" in t_lower:
            category = "Internships"
        else:
            category = self.default_category

        # 3. Organization
        org = "Federal Ministry of Labour & Employment / NELEX"
        # Search for Employer in text
        m_emp = re.search(r'Employer\s*:\s*([^<\n\r]+)', html, re.IGNORECASE)
        if m_emp:
            emp_name = m_emp.group(1).strip()
            if emp_name and len(emp_name) > 2:
                org = emp_name

        # 4. Description
        desc = ""
        m_desc = re.search(
            r'Job Description\s*(?:</h3>|</h2>|</b>|</strong>)?(.*?)(?:<h\d|<div\s+class=[\"\']col|<footer|<p>\s*Qualifications|\Z)',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if m_desc:
            desc = re.sub(r'<[^>]+>', ' ', m_desc.group(1)).strip()
            desc = unescape(' '.join(desc.split()))

        if not desc or len(desc) < 20:
            desc = f"Verified government-approved employment listing published via NELEX: {clean_title}."

        # 5. Qualifications & Eligibility
        eligibility = "Check official requirements on NELEX."
        m_qual = re.search(
            r'Qualifications and Requirements\s*(?:</h3>|</h2>|</b>|</strong>)?(.*?)(?:<h\d|<div\s+class=[\"\']col|<footer|<p>\s*Location|\Z)',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if m_qual:
            clean_qual = re.sub(r'<[^>]+>', ' ', m_qual.group(1)).strip()
            clean_qual = unescape(' '.join(clean_qual.split()))
            if clean_qual:
                eligibility = clean_qual[:500]


        # 6. Location
        location = "Nigeria (NELEX)"
        m_loc = re.search(r'Location\s*:\s*</?(?:strong|b|span|div)[^>]*>\s*([^<\n\r]+)', html, re.IGNORECASE)
        if m_loc:
            loc_val = m_loc.group(1).strip()
            if loc_val:
                location = loc_val

        # 7. Deadline
        parsed_deadline = None
        m_dead = re.search(r'Deadline\s*:\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})', html, re.IGNORECASE)
        if m_dead:
            parsed_deadline, _ = parse_date_value(m_dead.group(1))

        # 8. Education Level
        edu_level = "All Levels"
        if "degree" in eligibility.lower() or "b.sc" in eligibility.lower() or "hnd" in eligibility.lower():
            edu_level = "BSc / HND Graduate"
        elif "undergraduate" in eligibility.lower() or "student" in eligibility.lower():
            edu_level = "Undergraduate"

        # 9. Stable ID
        slug = source_url.rstrip("/").split("/")[-1].lower()
        clean_slug = re.sub(r'[^a-z0-9\-]+', '', slug)[:20]
        opp_id = f"OPP-NELEX-{clean_slug.upper()}"

        return NormalizedOpportunity(
            opportunity_id=opp_id,
            title=clean_title,
            category=category,
            organization=unescape(org).strip(),
            description=desc[:1000],
            eligibility=eligibility,
            education_level=edu_level,
            location=location,
            deadline=parsed_deadline,
            source_url=source_url,
            verified_at=datetime.now(timezone.utc),
            status="VERIFIED",
        )
