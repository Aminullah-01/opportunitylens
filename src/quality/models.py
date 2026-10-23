"""Data quality and verification data models for OpportunityLens."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
import json
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    """Severity classification for data quality issues."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LifecycleStatus(str, Enum):
    """Application lifecycle status derived from deadlines and official status."""

    UPCOMING = "UPCOMING"
    OPEN = "OPEN"
    CLOSING_SOON = "CLOSING_SOON"
    EXPIRED = "EXPIRED"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class VerificationStatus(str, Enum):
    """Source verification outcome status."""

    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BROKEN_LINK = "BROKEN_LINK"
    UNVERIFIABLE = "UNVERIFIABLE"
    NOT_CHECKED = "NOT_CHECKED"


class QualityStatus(str, Enum):
    """Overall data quality rating for an opportunity record."""

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


@dataclass
class QualityIssue:
    """An individual data quality or integrity issue identified on a record."""

    opportunity_id: str
    field_name: str
    severity: Severity
    issue_code: str
    message: str
    suggested_action: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert issue to serializable dictionary."""
        return {
            "opportunity_id": self.opportunity_id,
            "field_name": self.field_name,
            "severity": self.severity.value,
            "issue_code": self.issue_code,
            "message": self.message,
            "suggested_action": self.suggested_action,
        }


@dataclass
class LinkCheckResult:
    """Result of an HTTP reachability check on a source URL."""

    url: str
    is_reachable: bool
    http_status: Optional[int] = None
    verification_status: VerificationStatus = VerificationStatus.NOT_CHECKED
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: Optional[float] = None
    final_url: Optional[str] = None
    checked_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert check result to serializable dictionary."""
        return {
            "url": self.url,
            "is_reachable": self.is_reachable,
            "http_status": self.http_status,
            "verification_status": self.verification_status.value,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
            "final_url": self.final_url,
            "checked_at": self.checked_at,
        }


@dataclass
class RecordAuditResult:
    """Consolidated audit outcome for a single opportunity record."""

    opportunity_id: str
    title: str
    organization: str
    category: str
    source_url: str
    quality_status: QualityStatus
    lifecycle_status: LifecycleStatus
    verification_status: VerificationStatus
    issues: List[QualityIssue] = field(default_factory=list)
    link_result: Optional[LinkCheckResult] = None
    days_until_deadline: Optional[int] = None
    days_since_verified: Optional[int] = None
    is_stale: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert record audit result to serializable dictionary."""
        return {
            "opportunity_id": self.opportunity_id,
            "title": self.title,
            "organization": self.organization,
            "category": self.category,
            "source_url": self.source_url,
            "quality_status": self.quality_status.value,
            "lifecycle_status": self.lifecycle_status.value,
            "verification_status": self.verification_status.value,
            "issues": [issue.to_dict() for issue in self.issues],
            "link_result": self.link_result.to_dict() if self.link_result else None,
            "days_until_deadline": self.days_until_deadline,
            "days_since_verified": self.days_since_verified,
            "is_stale": self.is_stale,
        }


@dataclass
class QualityReportSummary:
    """Aggregated numerical metrics for an audit report."""

    total_records: int = 0
    passed_records: int = 0
    warning_records: int = 0
    failed_records: int = 0
    potential_duplicates: int = 0
    expired_opportunities: int = 0
    closing_soon_opportunities: int = 0
    open_opportunities: int = 0
    unknown_deadline_opportunities: int = 0
    stale_verification_records: int = 0
    source_urls_checked: int = 0
    reachable_sources: int = 0
    broken_link_candidates: int = 0
    unverifiable_sources: int = 0
    network_transient_failures: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary."""
        return asdict(self)


class _DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for dates and datetimes."""

    def default(self, o: Any) -> Any:
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        if isinstance(o, Enum):
            return o.value
        return super().default(o)


@dataclass
class DataQualityReport:
    """Comprehensive data quality and verification audit report."""

    generated_at: str
    report_scope: str
    dry_run: bool
    summary: QualityReportSummary = field(default_factory=QualityReportSummary)
    issues: List[QualityIssue] = field(default_factory=list)
    records: List[RecordAuditResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "generated_at": self.generated_at,
            "report_scope": self.report_scope,
            "dry_run": self.dry_run,
            "summary": self.summary.to_dict(),
            "issues": [i.to_dict() for i in self.issues],
            "records": [r.to_dict() for r in self.records],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent, cls=_DateTimeEncoder)

    def to_csv_rows(self) -> List[Dict[str, Any]]:
        """Flatten record audits into row dictionaries suitable for CSV export."""
        rows = []
        for r in self.records:
            issue_codes = ";".join(i.issue_code for i in r.issues)
            rows.append({
                "opportunity_id": r.opportunity_id,
                "title": r.title,
                "organization": r.organization,
                "category": r.category,
                "quality_status": r.quality_status.value,
                "lifecycle_status": r.lifecycle_status.value,
                "verification_status": r.verification_status.value,
                "is_stale": r.is_stale,
                "days_until_deadline": r.days_until_deadline if r.days_until_deadline is not None else "",
                "days_since_verified": r.days_since_verified if r.days_since_verified is not None else "",
                "issues_count": len(r.issues),
                "issue_codes": issue_codes,
                "source_url": r.source_url,
            })
        return rows

    def export_csv(self, file_path: str) -> None:
        """Export report records to a CSV file."""
        import csv
        rows = self.to_csv_rows()
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            else:
                f.write("opportunity_id,title,organization,category,quality_status\n")
