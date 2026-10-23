"""Data quality and verification pipeline orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from src.quality.models import (
    DataQualityReport,
    LifecycleStatus,
    QualityIssue,
    QualityReportSummary,
    QualityStatus,
    RecordAuditResult,
    Severity,
    VerificationStatus,
)
from src.quality.source_checker import SafeSourceChecker
from src.quality.validator import audit_batch_records

logger = logging.getLogger(__name__)


def run_quality_pipeline(
    records: List[Dict[str, Any]],
    report_scope: str = "in_memory",
    dry_run: bool = True,
    check_urls: bool = False,
    network_enabled: bool = False,
    stale_threshold_days: int = 30,
    reference_now: Optional[datetime] = None,
    rate_limit_delay_seconds: float = 0.0,
) -> DataQualityReport:
    """Run data quality validation, freshness checks, and optional link verification.

    Args:
        records: List of raw opportunity records.
        report_scope: Label identifying audit source (e.g. 'snowflake', 'raw_file', 'test').
        dry_run: Whether pipeline runs in dry-run mode (default True).
        check_urls: Whether to execute HTTP reachability checks on source URLs.
        network_enabled: Whether network requests are permitted.
        stale_threshold_days: Threshold in days for considering verification stale.
        reference_now: Deterministic reference timestamp.
        rate_limit_delay_seconds: Delay between HTTP link checks.

    Returns:
        Structured DataQualityReport with summary metrics and detailed issues.
    """
    now_dt = reference_now or datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    # 1. Run core data-quality and freshness audits on records
    audited_records, initial_issues = audit_batch_records(
        records,
        reference_now=now_dt,
        stale_threshold_days=stale_threshold_days,
    )

    # 2. Optional Source URL Reachability Checks
    urls_checked = 0
    reachable_sources = 0
    broken_links = 0
    unverifiable_sources = 0
    transient_failures = 0

    if check_urls and records:
        checker = SafeSourceChecker(
            network_enabled=network_enabled,
            rate_limit_delay_seconds=rate_limit_delay_seconds,
        )

        # Cache check results by URL to avoid querying the same domain multiple times in one run
        url_cache: Dict[str, Any] = {}

        for rec_result in audited_records:
            url = rec_result.source_url
            if not url or not rec_result.source_url.startswith(("http://", "https://")):
                continue

            if url in url_cache:
                link_res = url_cache[url]
            else:
                link_res = checker.check_url(url)
                url_cache[url] = link_res

            rec_result.link_result = link_res
            urls_checked += 1

            if link_res.is_reachable:
                reachable_sources += 1
            elif link_res.verification_status == VerificationStatus.BROKEN_LINK:
                broken_links += 1
                rec_result.verification_status = VerificationStatus.BROKEN_LINK
                # Add Quality Issue for broken link
                rec_result.issues.append(
                    QualityIssue(
                        opportunity_id=rec_result.opportunity_id,
                        field_name="source_url",
                        severity=Severity.ERROR,
                        issue_code="BROKEN_SOURCE_LINK",
                        message=f"Source URL is unreachable: {link_res.error_message}",
                        suggested_action="Verify or replace the application URL.",
                    )
                )
                rec_result.quality_status = QualityStatus.FAIL
            elif link_res.verification_status == VerificationStatus.UNVERIFIABLE:
                unverifiable_sources += 1
                rec_result.verification_status = VerificationStatus.UNVERIFIABLE
                rec_result.issues.append(
                    QualityIssue(
                        opportunity_id=rec_result.opportunity_id,
                        field_name="source_url",
                        severity=Severity.WARNING,
                        issue_code="UNVERIFIABLE_SOURCE_LINK",
                        message=f"Source URL could not be automated: {link_res.error_message}",
                        suggested_action="Manually review source URL in a web browser.",
                    )
                )

    # 3. Aggregate all final issues across all records
    final_issues: List[QualityIssue] = []
    for r in audited_records:
        final_issues.extend(r.issues)

    # 4. Compute Summary Metrics
    total = len(audited_records)
    passed_count = sum(1 for r in audited_records if r.quality_status == QualityStatus.PASS)
    warning_count = sum(1 for r in audited_records if r.quality_status == QualityStatus.WARNING)
    failed_count = sum(1 for r in audited_records if r.quality_status == QualityStatus.FAIL)

    dup_count = sum(
        1
        for i in final_issues
        if i.issue_code in ("DUPLICATE_OPPORTUNITY_ID", "DUPLICATE_OPPORTUNITY_CONTENT")
    )
    expired_count = sum(1 for r in audited_records if r.lifecycle_status == LifecycleStatus.EXPIRED)
    closing_soon_count = sum(1 for r in audited_records if r.lifecycle_status == LifecycleStatus.CLOSING_SOON)
    open_count = sum(1 for r in audited_records if r.lifecycle_status == LifecycleStatus.OPEN)
    unknown_deadline_count = sum(1 for r in audited_records if r.lifecycle_status == LifecycleStatus.UNKNOWN)
    stale_count = sum(1 for r in audited_records if r.is_stale)

    summary = QualityReportSummary(
        total_records=total,
        passed_records=passed_count,
        warning_records=warning_count,
        failed_records=failed_count,
        potential_duplicates=dup_count,
        expired_opportunities=expired_count,
        closing_soon_opportunities=closing_soon_count,
        open_opportunities=open_count,
        unknown_deadline_opportunities=unknown_deadline_count,
        stale_verification_records=stale_count,
        source_urls_checked=urls_checked,
        reachable_sources=reachable_sources,
        broken_link_candidates=broken_links,
        unverifiable_sources=unverifiable_sources,
        network_transient_failures=transient_failures,
    )

    return DataQualityReport(
        generated_at=now_iso,
        report_scope=report_scope,
        dry_run=dry_run,
        summary=summary,
        issues=final_issues,
        records=audited_records,
    )
