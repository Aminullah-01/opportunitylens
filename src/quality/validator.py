"""Comprehensive data quality, integrity, and contradiction auditing engine."""

from __future__ import annotations

from datetime import date, datetime, timezone
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.ingestion.models import CANONICAL_CATEGORIES, VALID_VERIFICATION_STATUSES
from src.quality.freshness import (
    evaluate_deadline_lifecycle,
    evaluate_verification_freshness,
    parse_deadline_date,
    parse_reference_datetime,
)
from src.quality.models import (
    LifecycleStatus,
    QualityIssue,
    QualityStatus,
    RecordAuditResult,
    Severity,
    VerificationStatus,
)
from src.utils import is_valid_url


def normalize_string(val: Any) -> str:
    """Normalize whitespace and strip string."""
    if val is None:
        return ""
    return re.sub(r"\s+", " ", str(val)).strip()


def normalize_key(val: Any) -> str:
    """Normalize string for deduplication keys (lowercase, alphanumerics only)."""
    return re.sub(r"[^a-z0-9]+", "", str(val or "").lower())


def audit_single_record(
    record: Dict[str, Any],
    reference_now: Optional[datetime | date | str] = None,
    stale_threshold_days: int = 30,
) -> RecordAuditResult:
    """Perform data quality, freshness, and metadata audits on an individual opportunity.

    Args:
        record: Opportunity dictionary (keys can be lower or uppercase).
        reference_now: Deterministic reference timestamp (defaults to current UTC).
        stale_threshold_days: Days after which verification is considered stale.

    Returns:
        RecordAuditResult containing quality rating, lifecycle status, and issues list.
    """
    ref_dt = parse_reference_datetime(reference_now)
    issues: List[QualityIssue] = []

    # Case-insensitive field access
    rec_lower = {str(k).lower(): v for k, v in record.items()}

    raw_id = normalize_string(rec_lower.get("opportunity_id"))
    opp_id = raw_id if raw_id else "UNKNOWN"

    raw_title = normalize_string(rec_lower.get("title"))
    raw_org = normalize_string(rec_lower.get("organization"))
    raw_cat = normalize_string(rec_lower.get("category"))
    raw_desc = normalize_string(rec_lower.get("description"))
    raw_elig = normalize_string(rec_lower.get("eligibility"))
    raw_url = normalize_string(rec_lower.get("source_url"))
    raw_status = normalize_string(rec_lower.get("status") or rec_lower.get("verification_status"))
    raw_deadline = rec_lower.get("deadline")
    raw_verified = rec_lower.get("verified_at")

    # 1. Title Audit
    if not raw_title:
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="title",
                severity=Severity.ERROR,
                issue_code="MISSING_TITLE",
                message="Title is missing or contains only whitespace.",
                suggested_action="Provide a concise, official opportunity title.",
            )
        )

    # 2. Organization Audit
    if not raw_org or raw_org.lower() in ("not specified", "unspecified", "n/a", "none"):
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="organization",
                severity=Severity.ERROR,
                issue_code="MISSING_ORGANIZATION",
                message="Organization name is missing, unspecified, or placeholder.",
                suggested_action="Specify the sponsoring company, government ministry, or institution.",
            )
        )

    # 3. Category Audit
    matched_cat = None
    if not raw_cat:
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="category",
                severity=Severity.ERROR,
                issue_code="MISSING_CATEGORY",
                message="Category is missing.",
                suggested_action=f"Assign one of canonical categories: {', '.join(CANONICAL_CATEGORIES)}.",
            )
        )
    else:
        for c in CANONICAL_CATEGORIES:
            if raw_cat.lower() == c.lower():
                matched_cat = c
                break
        if not matched_cat:
            issues.append(
                QualityIssue(
                    opportunity_id=opp_id,
                    field_name="category",
                    severity=Severity.ERROR,
                    issue_code="INVALID_CATEGORY",
                    message=f"Category '{raw_cat}' is not an approved canonical category.",
                    suggested_action=f"Map to one of: {', '.join(CANONICAL_CATEGORIES)}.",
                )
            )

    # 4. Source URL Audit
    if not raw_url:
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="source_url",
                severity=Severity.ERROR,
                issue_code="MISSING_URL",
                message="Source URL is missing or blank.",
                suggested_action="Provide the authoritative public application URL.",
            )
        )
    elif not is_valid_url(raw_url):
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="source_url",
                severity=Severity.ERROR,
                issue_code="INVALID_URL_SYNTAX",
                message=f"Source URL '{raw_url}' is not a valid HTTP or HTTPS web address.",
                suggested_action="Ensure the URL starts with http:// or https:// and has a valid domain.",
            )
        )

    # 5. Description Audit
    if not raw_desc:
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="description",
                severity=Severity.ERROR,
                issue_code="EMPTY_DESCRIPTION",
                message="Opportunity description is missing.",
                suggested_action="Add a summary describing the program and benefits.",
            )
        )
    elif len(raw_desc) < 20:
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="description",
                severity=Severity.WARNING,
                issue_code="INCOMPLETE_DESCRIPTION",
                message=f"Description is very brief ({len(raw_desc)} characters).",
                suggested_action="Expand description with comprehensive details for applicants.",
            )
        )

    # 6. Eligibility Criteria Audit
    if not raw_elig or raw_elig.lower() in ("check official source.", "check the official source.", "none", "n/a"):
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="eligibility",
                severity=Severity.WARNING,
                issue_code="VAGUE_ELIGIBILITY",
                message="Eligibility criteria are vague or use placeholder text.",
                suggested_action="Document explicit academic, CGPA, regional, or level prerequisites.",
            )
        )

    # 7. Verification Status Audit
    raw_ver_field = normalize_string(rec_lower.get("verification_status"))
    raw_status_field = normalize_string(rec_lower.get("status"))

    if raw_ver_field:
        clean_ver_status = raw_ver_field.upper()
    elif raw_status_field and raw_status_field.upper() in VALID_VERIFICATION_STATUSES:
        clean_ver_status = raw_status_field.upper()
    elif raw_status_field and raw_status_field.title() in ("Open", "Closing Soon", "Closed", "Unknown"):
        clean_ver_status = "UNVERIFIED"
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="verification_status",
                severity=Severity.INFO,
                issue_code="LIFECYCLE_STATUS_SUPPLIED",
                message=f"Application lifecycle status '{raw_status_field}' was supplied in status field; verification status defaulted to UNVERIFIED.",
                suggested_action=f"Specify verification status as one of: {', '.join(VALID_VERIFICATION_STATUSES)}.",
            )
        )
    else:
        clean_ver_status = raw_status_field.upper() if raw_status_field else "UNVERIFIED"

    if clean_ver_status not in VALID_VERIFICATION_STATUSES:
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="status",
                severity=Severity.ERROR,
                issue_code="INVALID_VERIFICATION_STATUS",
                message=f"Status '{raw_status_field or raw_ver_field}' is invalid. Expected one of: {', '.join(VALID_VERIFICATION_STATUSES)}.",
                suggested_action=f"Update status to one of: {', '.join(VALID_VERIFICATION_STATUSES)}.",
            )
        )

    # 8. Deadline & Lifecycle Audit
    lifecycle_status, days_until_deadline = evaluate_deadline_lifecycle(
        deadline_val=raw_deadline,
        source_status=raw_status,
        reference_now=ref_dt,
    )
    parsed_deadline, deadline_err = parse_deadline_date(raw_deadline)
    if deadline_err:
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="deadline",
                severity=Severity.ERROR,
                issue_code="INVALID_DEADLINE_FORMAT",
                message=deadline_err,
                suggested_action="Format deadline as ISO date YYYY-MM-DD.",
            )
        )
    elif parsed_deadline is None:
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="deadline",
                severity=Severity.WARNING,
                issue_code="MISSING_DEADLINE",
                message="Opportunity has no deadline specified; lifecycle is treated as UNKNOWN.",
                suggested_action="Specify closing deadline or explicitly mark as rolling cohort.",
            )
        )

    # 9. Verification Freshness Audit
    is_stale, days_since_verified, freshness_msg = evaluate_verification_freshness(
        verified_at_val=raw_verified,
        reference_now=ref_dt,
        stale_threshold_days=stale_threshold_days,
    )
    if freshness_msg:
        if "future" in freshness_msg.lower():
            issues.append(
                QualityIssue(
                    opportunity_id=opp_id,
                    field_name="verified_at",
                    severity=Severity.ERROR,
                    issue_code="FUTURE_VERIFICATION_TIMESTAMP",
                    message=freshness_msg,
                    suggested_action="Correct timestamp to reflect the actual time audit was conducted in UTC.",
                )
            )
        else:
            issues.append(
                QualityIssue(
                    opportunity_id=opp_id,
                    field_name="verified_at",
                    severity=Severity.WARNING,
                    issue_code="STALE_VERIFICATION",
                    message=freshness_msg,
                    suggested_action=f"Re-verify opportunity against primary source listing.",
                )
            )

    # 10. Contradiction Audits
    # Contradiction A: Status marked VERIFIED but has blocking errors
    has_errors = any(i.severity == Severity.ERROR for i in issues)
    if clean_ver_status == "VERIFIED" and has_errors:
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="status",
                severity=Severity.ERROR,
                issue_code="CONTRADICTORY_VERIFICATION_STATE",
                message="Record is marked VERIFIED but fails critical data quality checks.",
                suggested_action="Fix blocking validation errors or downgrade status to NEEDS_REVIEW.",
            )
        )

    # Contradiction B: Marked Closed, but deadline is far in future (> 60 days)
    if lifecycle_status == LifecycleStatus.CLOSED and days_until_deadline and days_until_deadline > 60:
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="status",
                severity=Severity.WARNING,
                issue_code="CONTRADICTORY_LIFECYCLE_STATUS",
                message=f"Opportunity is marked Closed but deadline is {days_until_deadline} days in the future.",
                suggested_action="Verify if the application window closed early or update the deadline.",
            )
        )

    # Contradiction C: Deadline expired over a year ago (> 365 days) but still marked Open
    if parsed_deadline and days_until_deadline and days_until_deadline < -365:
        issues.append(
            QualityIssue(
                opportunity_id=opp_id,
                field_name="deadline",
                severity=Severity.WARNING,
                issue_code="ANCIENT_EXPIRED_DEADLINE",
                message=f"Deadline passed over a year ago ({abs(days_until_deadline)} days ago).",
                suggested_action="Archive the opportunity or update with the current cohort intake cycle.",
            )
        )

    # Determine consolidated QualityStatus
    if any(i.severity == Severity.ERROR for i in issues):
        quality_status = QualityStatus.FAIL
    elif any(i.severity == Severity.WARNING for i in issues):
        quality_status = QualityStatus.WARNING
    else:
        quality_status = QualityStatus.PASS

    # Determine VerificationStatus
    if clean_ver_status == "VERIFIED" and quality_status != QualityStatus.FAIL:
        ver_status = VerificationStatus.VERIFIED
    elif clean_ver_status == "NEEDS_REVIEW":
        ver_status = VerificationStatus.NEEDS_REVIEW
    else:
        ver_status = VerificationStatus.NEEDS_REVIEW

    return RecordAuditResult(
        opportunity_id=opp_id,
        title=raw_title or "Untitled",
        organization=raw_org or "Not specified",
        category=matched_cat or (raw_cat or "Other"),
        source_url=raw_url,
        quality_status=quality_status,
        lifecycle_status=lifecycle_status,
        verification_status=ver_status,
        issues=issues,
        days_until_deadline=days_until_deadline,
        days_since_verified=days_since_verified,
        is_stale=is_stale,
    )


def audit_batch_records(
    records: List[Dict[str, Any]],
    reference_now: Optional[datetime | date | str] = None,
    stale_threshold_days: int = 30,
) -> Tuple[List[RecordAuditResult], List[QualityIssue]]:
    """Audit a list of opportunity records, detecting duplicates across the batch.

    Args:
        records: List of raw opportunity dictionaries.
        reference_now: Deterministic reference timestamp.
        stale_threshold_days: Days after which verification is considered stale.

    Returns:
        Tuple of (audited_records, all_aggregated_issues).
    """
    ref_dt = parse_reference_datetime(reference_now)
    audited_list: List[RecordAuditResult] = []

    # Track duplicates
    seen_ids: Dict[str, List[int]] = {}
    seen_content_keys: Dict[str, List[int]] = {}

    for idx, rec in enumerate(records):
        result = audit_single_record(
            rec, reference_now=ref_dt, stale_threshold_days=stale_threshold_days
        )
        audited_list.append(result)

        # Track ID duplicates
        if result.opportunity_id and result.opportunity_id != "UNKNOWN":
            seen_ids.setdefault(result.opportunity_id, []).append(idx)

        # Track content duplicates: normalized (organization + title + source_url)
        c_org = normalize_key(result.organization)
        c_title = normalize_key(result.title)
        c_url = normalize_key(result.source_url)
        if c_org and c_title:
            content_key = f"{c_org}::{c_title}::{c_url}"
            seen_content_keys.setdefault(content_key, []).append(idx)

    # Flag duplicate IDs (Hard ERROR)
    for opp_id, indices in seen_ids.items():
        if len(indices) > 1:
            for idx in indices:
                issue = QualityIssue(
                    opportunity_id=opp_id,
                    field_name="opportunity_id",
                    severity=Severity.ERROR,
                    issue_code="DUPLICATE_OPPORTUNITY_ID",
                    message=f"Duplicate opportunity_id '{opp_id}' appears {len(indices)} times in dataset.",
                    suggested_action="Ensure opportunity IDs are unique; regenerate using stable hashing.",
                )
                audited_list[idx].issues.append(issue)
                audited_list[idx].quality_status = QualityStatus.FAIL

    # Flag content duplicates (WARNING)
    for key, indices in seen_content_keys.items():
        if len(indices) > 1:
            for idx in indices:
                # Avoid adding redundant content duplicate warning if already flagged as duplicate ID
                already_has_dup_id = any(
                    i.issue_code == "DUPLICATE_OPPORTUNITY_ID"
                    for i in audited_list[idx].issues
                )
                if not already_has_dup_id:
                    issue = QualityIssue(
                        opportunity_id=audited_list[idx].opportunity_id,
                        field_name="title",
                        severity=Severity.WARNING,
                        issue_code="DUPLICATE_OPPORTUNITY_CONTENT",
                        message=f"Opportunity appears to be a duplicate of another listing by organization, title, and URL.",
                        suggested_action="Review and deduplicate entries using idempotent MERGE.",
                    )
                    audited_list[idx].issues.append(issue)
                    if audited_list[idx].quality_status == QualityStatus.PASS:
                        audited_list[idx].quality_status = QualityStatus.WARNING

    # Collect all issues across all records
    all_issues: List[QualityIssue] = []
    for r in audited_list:
        all_issues.extend(r.issues)

    return audited_list, all_issues
