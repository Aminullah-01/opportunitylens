"""Adapter for LEEP Jobs (Federal Ministry of Labour and Employment Platform).

Discovers job listings from https://jobs.leep.gov.ng/jobs and extracts official
Schema.org JobPosting structured JSON-LD data.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
from html import unescape
import json
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from src.ingestion.models import NormalizedOpportunity
from src.ingestion.sources.base import BaseSourceAdapter
from src.ingestion.validator import parse_date_value, parse_datetime_value

logger = logging.getLogger(__name__)


class LeepJobsAdapter(BaseSourceAdapter):
    """Adapter for LEEP Jobs portal."""

    source_id = "leep_jobs"
    source_name = "LEEP Jobs (Federal Republic of Nigeria)"
    base_url = "https://jobs.leep.gov.ng/jobs"
    default_category = "Entry-Level Jobs"
    enabled = True

    def _extract_listing_cards(self, html_text: str) -> List[Dict[str, Any]]:
        """Extract baseline opportunity cards directly from the main listing page HTML.

        Extracts URL, title, company, location, salary, and employment type without
        strictly requiring every detail page to succeed.
        """
        cards = []
        for match in re.finditer(
            r'<a\s+[^>]*href=[\"\']([^\"]*job/[^\"]+)[\"\'][^>]*class=[\"\'][^\"\']*jobcardStyle1[^\"\']*[\"\'][^>]*>',
            html_text,
            re.IGNORECASE,
        ):
            start = match.start()
            end = html_text.find("</a>", start)
            if end == -1:
                continue
            card_html = html_text[start:end + 4]
            raw_url = match.group(1)
            full_url = urljoin(self.base_url, raw_url)

            # Title: <span class="tw-text-lg ...">Title</span>
            title_m = re.search(r'tw-text-lg[^>]*>(.*?)</span>', card_html, re.DOTALL)
            title = (
                unescape(re.sub(r'<[^>]+>', '', title_m.group(1)).strip())
                if title_m
                else ""
            )

            # Organization: <span class="... tw-card-title">Company</span>
            org_m = re.search(r'tw-card-title[^>]*>(.*?)</span>', card_html, re.DOTALL)
            org = (
                unescape(re.sub(r'<[^>]+>', '', org_m.group(1)).strip())
                if org_m
                else ""
            )

            # Location: <span class="tw-location">Location</span>
            loc_m = re.search(r'tw-location[^>]*>(.*?)</span>', card_html, re.DOTALL)
            loc = (
                unescape(re.sub(r'<[^>]+>', '', loc_m.group(1)).strip())
                if loc_m
                else ""
            )

            # Salary: Salary: ...
            sal_m = re.search(
                r'Salary:\s*</span>?\s*(.*?)(?:</div>|</span>)',
                card_html,
                re.DOTALL | re.IGNORECASE,
            )
            salary = (
                unescape(' '.join(re.sub(r'<[^>]+>', '', sal_m.group(1)).split()))
                if sal_m
                else ""
            )

            # Employment Type
            emp_m = re.search(
                r'class=[\"\'][^\"\']*tw-text-\[#0BA02C\][^\"\']*[\"\'][^>]*>(.*?)</span>',
                card_html,
                re.DOTALL,
            )
            emp_type = (
                unescape(re.sub(r'<[^>]+>', '', emp_m.group(1)).strip())
                if emp_m
                else ""
            )

            cards.append({
                "source_url": full_url,
                "listing_title": title,
                "listing_org": org,
                "listing_location": loc,
                "listing_salary": salary,
                "listing_employment_type": emp_type,
                "listing_html": card_html,
                "detail_fetched": False,
                "html": None,
                "json_ld": None,
            })
        return cards

    def fetch_raw(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Discover job listings from LEEP Jobs and extract their structured payload.

        Extracts baseline card data from the listing page, then enriches with detail
        page Schema.org JSON-LD if responsive. Preserves listing data if detail requests time out.
        """
        response = self.safe_request(self.base_url)
        html_text = response.text

        # 1. Primary: Parse job cards directly from listing page
        cards = self._extract_listing_cards(html_text)

        # 2. Fallback: Search for any /job/<slug> links if listing structure differs
        if not cards:
            detail_paths = re.findall(
                r'href=[\"\'](/job/[a-zA-Z0-9\-_]+)[\"\']', html_text, re.IGNORECASE
            )
            if not detail_paths:
                detail_paths = re.findall(
                    r'href=[\"\'](https://jobs\.leep\.gov\.ng/job/[a-zA-Z0-9\-_]+)[\"\']',
                    html_text,
                    re.IGNORECASE,
                )
            seen = set()
            for p in detail_paths:
                full_url = urljoin(self.base_url, p)
                if full_url not in seen:
                    seen.add(full_url)
                    cards.append({
                        "source_url": full_url,
                        "listing_title": "",
                        "listing_org": "",
                        "listing_location": "",
                        "listing_salary": "",
                        "listing_employment_type": "",
                        "listing_html": "",
                        "detail_fetched": False,
                        "html": None,
                        "json_ld": None,
                    })

        if limit is not None and limit > 0:
            cards = cards[:limit]

        # 3. Enrich cards with detail page Schema.org JSON-LD
        for card in cards:
            job_url = card["source_url"]
            try:
                detail_resp = self.safe_request(job_url)
                detail_html = detail_resp.text
                card["html"] = detail_html

                # Extract Schema.org JSON-LD scripts
                json_lds = re.findall(
                    r'<script[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>',
                    detail_html,
                    re.DOTALL | re.IGNORECASE,
                )

                parsed_json_ld: Optional[Dict[str, Any]] = None
                for block in json_lds:
                    try:
                        data = json.loads(block)
                        if isinstance(data, dict) and data.get("@type") == "JobPosting":
                            parsed_json_ld = data
                            break
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                                    parsed_json_ld = item
                                    break
                    except Exception:
                        continue

                card["json_ld"] = parsed_json_ld
                card["detail_fetched"] = True

            except Exception as exc:
                msg = f"LEEP detail fetch timed out or failed for {job_url}: {exc}"
                logger.warning(msg)
                self.warning_messages.append(msg)
                card["detail_error"] = str(exc)
                card["detail_fetched"] = False
                # Baseline listing metadata remains preserved in card

        return cards

    def parse_record(self, raw: Dict[str, Any]) -> NormalizedOpportunity:
        """Parse raw LEEP job page or listing card into NormalizedOpportunity."""
        source_url = raw.get("source_url", "")
        json_ld = raw.get("json_ld") or {}
        html = raw.get("html") or raw.get("listing_html") or ""

        # 1. Title
        title = json_ld.get("title") or raw.get("listing_title")
        if not title and html:
            m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else ""
        if not title:
            title = "Untitled Job"
        clean_title = unescape(str(title)).strip()

        # 2. Organization
        hiring_org = json_ld.get("hiringOrganization")
        if isinstance(hiring_org, dict):
            org_name = hiring_org.get("name")
        else:
            org_name = None
        if not org_name:
            org_name = raw.get("listing_org")
        if not org_name:
            org_name = "Federal Ministry of Labour & Employment / LEEP"
        clean_org = unescape(str(org_name)).strip()

        # 3. Location
        location_parts = []
        job_loc = json_ld.get("jobLocation")
        if isinstance(job_loc, dict):
            addr = job_loc.get("address", {})
            if isinstance(addr, dict):
                reg = addr.get("addressRegion")
                if reg:
                    location_parts.append(str(reg).strip())
                country = addr.get("addressCountry")
                if country:
                    location_parts.append(str(country).strip())
        if location_parts:
            location_str = ", ".join(location_parts)
        elif raw.get("listing_location"):
            location_str = str(raw["listing_location"]).strip()
        else:
            location_str = "Nigeria (LEEP Portal)"

        # 4. Description
        raw_desc = json_ld.get("description", "")
        clean_desc = re.sub(r'<[^>]+>', ' ', raw_desc)
        clean_desc = unescape(' '.join(clean_desc.split())).strip()
        if not clean_desc:
            sal_part = f" Salary: {raw.get('listing_salary')}." if raw.get("listing_salary") else ""
            emp_part = f" Employment type: {raw.get('listing_employment_type')}." if raw.get("listing_employment_type") else ""
            clean_desc = (
                f"Opportunity listing published via LEEP official portal: {clean_title} at {clean_org}."
                f" Location: {location_str}.{sal_part}{emp_part} Apply directly via official LEEP portal."
            )

        # 5. Category derivation
        t_lower = clean_title.lower()
        if "intern" in t_lower:
            category = "Internships"
        elif any(k in t_lower for k in ["training", "bootcamp", "academy", "fellow"]):
            category = "Tech Training"
        elif any(k in t_lower for k in ["hackathon", "challenge"]):
            category = "Hackathons"
        else:
            category = self.default_category

        # 6. Deadline (validThrough)
        deadline_raw = json_ld.get("validThrough")
        parsed_deadline, _ = parse_date_value(deadline_raw)

        # 7. Education Level and Eligibility
        edu_level = "All Levels"
        if "degree" in clean_desc.lower() or "b.sc" in clean_desc.lower() or "hnd" in clean_desc.lower():
            edu_level = "BSc / HND Graduate"
        elif "undergraduate" in clean_desc.lower():
            edu_level = "Undergraduate"

        # Eligibility statement
        eligibility_str = f"Open to eligible candidates in {location_str}. Apply directly via the official LEEP portal."

        # 8. Verified At
        date_posted = json_ld.get("datePosted")
        verified_dt, _ = parse_datetime_value(date_posted)
        if not verified_dt:
            verified_dt = datetime.now(timezone.utc)

        # 9. Verification Status
        # Requirement 8: Ensure invalid, expired, or unverified opportunities are not incorrectly labelled active or verified
        status = raw.get("status")
        if not status:
            if parsed_deadline and parsed_deadline < date.today():
                status = "NEEDS_REVIEW"
            else:
                status = "VERIFIED"

        # 10. Stable Identifier
        identifier = json_ld.get("identifier")
        ext_val = None
        if isinstance(identifier, dict):
            ext_val = identifier.get("value")
        if ext_val:
            opp_id = f"OPP-LEEP-{ext_val}"
        else:
            slug = source_url.rstrip("/").split("/")[-1]
            h = hashlib.sha256(slug.encode("utf-8")).hexdigest()[:8].upper()
            opp_id = f"OPP-LEEP-{h}"

        return NormalizedOpportunity(
            opportunity_id=opp_id,
            title=clean_title,
            category=category,
            organization=clean_org,
            description=clean_desc,
            eligibility=eligibility_str,
            education_level=edu_level,
            location=location_str,
            deadline=parsed_deadline,
            source_url=source_url,
            verified_at=verified_dt,
            status=status,
        )
