# OpportunityLens — Operations & Observability Guide (Phase 6)

This document provides production readiness, operational monitoring, scheduling, and health check guidelines for **OpportunityLens**.

---

## 1. System Health Monitoring

OpportunityLens provides an offline-first system health diagnostic tool that inspects local runtime, configuration readiness, and storage permissions without requiring external network connectivity by default.

### Running Health Checks via CLI

```bash
# Basic offline health check (table format)
python -m src.monitoring.cli --health

# Machine-readable JSON output (ideal for monitoring agents and CI)
python -m src.monitoring.cli --health --json

# Opt-in live connectivity check against Snowflake and AI provider
python -m src.monitoring.cli --check-connectivity --check-inference --timeout 5.0
```

### Component Status Definitions

| Status | Meaning |
|---|---|
| `HEALTHY` | Component is operational, configured, and responsive. |
| `DEGRADED` | Component is partially operational or an optional external provider (Snowflake or AI) is unconfigured. The application remains fully functional in offline/demo mode with deterministic fallbacks. |
| `UNAVAILABLE` | A configured component failed a live connectivity test, or a critical local runtime requirement is missing. |
| `NOT_CHECKED` | Live network connectivity check was skipped to preserve fast, offline execution. |

---

## 2. Operational Audit Runner

The operational audit runner (`src/quality/runner.py`) automates data quality and freshness audits across different sources (`demo`, `file`, `snowflake`) and persists timestamped reports.

### CLI Usage

```bash
# Run audit against demo dataset (default offline mode)
python -m src.quality.runner --source demo

# Run audit against raw data file and generate CSV alongside JSON
python -m src.quality.runner --source file --input-file data/raw_opportunities.json --csv

# Run audit against live Snowflake table (offline URL checks)
python -m src.quality.runner --source snowflake --no-network

# Opt-in to live external link reachability verification
python -m src.quality.runner --source demo --check-urls
```

### Exit Codes

The audit runner returns deterministic process exit codes for orchestration in CI/CD and cron:

| Exit Code | Name | Description |
|---|---|---|
| `0` | `EXIT_SUCCESS` | All inspected records passed validation, or only acceptable non-blocking warnings were detected. |
| `1` | `EXIT_EXECUTION_FAILURE` | Audit execution failed (e.g. unreadable file, missing database credentials, concurrency lock conflict). |
| `2` | `EXIT_BLOCKING_DATA_ERRORS` | One or more records failed critical data quality checks (`FAIL` status). Immediate attention required. |
| `3` | `EXIT_QUALITY_WARNINGS` | Returned when `--fail-on-warnings` is specified and one or more quality warnings or stale records exist. |

---

## 3. Scheduled Execution & Overlap Prevention

### Overlap Prevention (Process Locking)
To prevent concurrent audit jobs from colliding or causing resource contention, the runner uses a lightweight PID-based file lock at `reports/audit/.audit_runner.lock`.

- When a run begins, it writes its process ID (PID) to the lock file.
- If a subsequent job starts while the lock exists:
  - It checks if the PID is still actively running.
  - If active: it aborts gracefully with exit code `1` and logs an alert.
  - If the previous process terminated abnormally (stale lock): it logs a warning, safely reclaims the lock, and proceeds.
- The lock file is automatically deleted upon normal completion or exception handling.

### Sample Cron Configuration

To run an operational audit every night at 02:00 UTC without network link checks:

```cron
# /etc/cron.d/opportunitylens-audit
# Run nightly Snowflake data audit at 02:00 UTC
0 2 * * * ameenullah cd /home/ameenullah/projects/opportunitylens && .venv/bin/python -m src.quality.runner --source snowflake --no-network --output-dir reports/audit >> /var/log/opportunitylens_audit.log 2>&1
```

For demo/file-based evaluation:
```cron
# Hourly file data audit
0 * * * * ameenullah cd /home/ameenullah/projects/opportunitylens && .venv/bin/python -m src.quality.runner --source file --input-file data/raw_opportunities.json >> /var/log/opportunitylens_audit.log 2>&1
```

---

## 4. Report Retention & Rotation Policy

By default, audit reports are saved to `reports/audit/` with timestamped filenames:
`audit_report_<source>_YYYYMMDD_HHMMSS.json` (and `.csv`).

### Retention Recommendation
- **High-frequency audits (hourly):** Retain reports for 7 days.
- **Daily scheduled audits:** Retain reports for 30–90 days for compliance and quality tracking.

### Logrotate Example

To automatically rotate output logs and purge old report artifacts:

```conf
# /etc/logrotate.d/opportunitylens
/var/log/opportunitylens_audit.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
}
```

To purge audit JSON reports older than 30 days:
```bash
find /home/ameenullah/projects/opportunitylens/reports/audit -name "audit_report_*.json" -mtime +30 -delete
```

---

## 5. Structured Logging & Secret Redaction

The operational telemetry engine (`src/monitoring/logging.py`) formats all log entries as structured JSON with UTC timestamps and sanitizes sensitive data:

- **Redacted Substrings:**
  - `Bearer <token>` replaced with `Bearer [REDACTED]`
  - `hf_<token>` replaced with `hf_[REDACTED]`
  - Passwords and connection secrets in key-value pairs replaced with `[REDACTED]`
  - Dictionaries with keys matching `password`, `secret`, `token`, `key`, `auth` automatically sanitized.
- **Diagnostics vs. Safety:** Full opportunity descriptions are never emitted in operational logs. Detailed error messages are preserved safely for developers while user-facing alerts remain clear and actionable.

---

## 6. Optional Notification Hooks

The notification subsystem (`src/monitoring/notifications.py`) provides an isolated alert interface that dispatches notifications when significant anomalies occur.

### Built-in Channels
- `NullNotificationChannel`: Default silent channel (used during automated tests).
- `LogNotificationChannel`: Dispatches alerts directly to the structured operational log.

### Supported Alert Triggers
1. **Blocking Data Quality Errors (`BLOCKING_DATA_ERRORS`):** Triggered when one or more records fail validation.
2. **Elevated Stale Records (`STALE_RECORDS_SURGE`):** Triggered when stale verification count exceeds threshold (default: 10).
3. **Unreachable URLs (`BROKEN_LINKS_DETECTED`):** Triggered when broken link candidate count exceeds threshold (default: 5).
4. **Pipeline Crash (`AUDIT_EXECUTION_FAILURE`):** Critical alert dispatched if the pipeline fails during execution.

### Extending with Webhook / Slack Notifications

To add an external webhook (e.g. Slack or Discord), implement `NotificationChannel`:

```python
import urllib.request
import json
from src.monitoring.notifications import NotificationChannel, NotificationEvent

class SlackWebhookChannel(NotificationChannel):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, event: NotificationEvent) -> bool:
        payload = {
            "text": f"*{event.title}* [{event.severity.value}]\n{event.summary}",
            "attachments": [{"fields": [{"title": k, "value": str(v), "short": True} for k, v in event.metrics.items()]}]
        }
        req = urllib.request.Request(
            self.webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.status == 200
        except Exception:
            return False
```
