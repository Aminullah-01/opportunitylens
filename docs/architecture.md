# OpportunityLens — System Architecture

**Tagline:** Find opportunities. Understand your chances. Take your next step.  
**Track:** Best Open-Source AI Project with Snowflake (Hacktoberfest Hack Day Gombe)

---

## 1. Executive Summary

OpportunityLens is an AI-powered opportunity discovery platform tailored for Nigerian tertiary students and early-career talents. The platform aggregates scholarships, internships, subsidized technical training programs, hackathons, and entry-level positions into a unified, searchable, and AI-assisted portal.

This project is built iteratively across distinct phases to demonstrate:
1. A real, freely accessible dataset hosted in Snowflake.
2. The practical application of Snowflake CoCo for SQL exploration, optimization, and pipeline generation.
3. An open-weight AI evaluation layer using Hugging Face Inference Providers / OpenAI-compatible APIs.
4. Clean, reproducible open-source software engineering.

---

## 2. Phase 5 Architecture (Current State)

Phase 5 introduces **automated data quality auditing, freshness evaluation, and safe source link verification** without mutating production databases. It enforces strict separation between lifecycle, verification, and data quality states, defends against Server-Side Request Forgery (SSRF), and provides an offline-first CLI and reporting pipeline.

### Component Overview

```mermaid
graph TD
    User([Student / Applicant / Auditor]) -->|Browser HTTP / WebSocket| StreamlitUI[Streamlit Application app.py]
    AuditorCLI[Quality CLI src/quality/cli.py] --> QualityPipeline[Quality Pipeline src/quality/pipeline.py]
    
    subgraph Data & Storage Layer
        RawData[(data/raw_opportunities.json)] --> IngestionCLI[CLI / Ingestion Pipeline src/ingestion/]
        IngestionCLI --> Validator[Validator & Normalizer src/ingestion/validator.py]
        Validator --> Dedup[In-Batch & Key Deduplicator]
        Dedup -->|Parameterized MERGE| SnowflakeTable[(Snowflake OPPORTUNITIES Table)]
    end

    subgraph UI & Caching Layer
        StreamlitUI --> Cache[@st.cache_data TTL 300s]
        Cache --> DBModule[Snowflake Access src/db.py]
        StreamlitUI --> AnalyticsEngine[Analytics Engine src/analytics.py]
        StreamlitUI --> Utils[Helper Utilities src/utils.py]
        StreamlitUI --> Config[Configuration Module src/config.py]
        DBModule -->|fetch_opportunities| SnowflakeTable
    end

    subgraph Phase 4: Matching & AI Guidance Layer
        StreamlitUI --> ProfileForm[Student Profile in Session State]
        StreamlitUI --> QueryParser[Query Parser src/matching/search.py]
        ProfileForm --> MatchService[Match Service src/matching/service.py]
        QueryParser --> MatchService
        SnowflakeTable -.->|Candidate Records| MatchService
        MatchService --> Scorer[Deterministic 6-Factor Scorer src/matching/scorer.py]
        MatchService --> EligibilityEngine[Eligibility Engine src/matching/eligibility.py]
        MatchService --> HFClient[HF Inference / Deterministic Fallback]
        HFClient --> StreamlitUI
    end

    subgraph Phase 5: Data Quality & Verification Layer
        StreamlitUI --> QualityPipeline
        SnowflakeTable -->|Read-Only Parameterized Query| SnowflakeAudit[Snowflake Audit src/quality/snowflake_audit.py]
        SnowflakeAudit --> QualityPipeline
        RawData --> QualityPipeline
        
        QualityPipeline --> DataAuditor[Data Quality Auditor src/quality/validator.py]
        QualityPipeline --> FreshnessEngine[Freshness & Lifecycle Evaluator src/quality/freshness.py]
        QualityPipeline --> SourceChecker[SSRF-Defended Link Checker src/quality/source_checker.py]
        
        SourceChecker -->|Opt-In HTTP Checks| PublicWeb[(Public Web Portals)]
        QualityPipeline --> QualityReport[JSON / CSV Audit Report]
        QualityPipeline --> StreamlitUI
    end
```

### Modules in Phase 5

- **`src/quality/`**: Dedicated data quality and verification package:
  - `models.py`: Data models (`LifecycleStatus`, `VerificationStatus`, `QualityStatus`, `QualityIssue`, `LinkCheckResult`, `RecordAuditResult`, `DataQualityReport`).
  - `validator.py`: Comprehensive integrity rules (missing titles, invalid categories, short descriptions, placeholder eligibility, duplicate IDs, duplicate content, and contradiction rules).
  - `freshness.py`: Deterministic deadline lifecycle evaluation (`OPEN`, `CLOSING_SOON`, `EXPIRED`, `CLOSED`, `UNKNOWN`), UTC normalization, stale verification detection (>30 days), and future timestamp anomaly detection.
  - `source_checker.py`: Safe, timeout-controlled HTTP reachability checker protected against Server-Side Request Forgery (SSRF) with private/loopback/metadata IP blocking and redirect revalidation.
  - `snowflake_audit.py`: Read-only, parameterized queries against `OPPORTUNITYLENS_DB.APP.OPPORTUNITIES` without destructive mutations.
  - `pipeline.py`: Reusable pipeline orchestrating validation, freshness, optional link checking, and report aggregation.
  - `cli.py`: Standalone CLI runner with `--source`, `--dry-run`, `--check-urls`, `--output`, and `--format`.
- **`sql/05_phase5_verification_schema.sql`**: Optional, non-destructive versioned migration script documenting in-place metadata columns (`LAST_CHECKED_AT`, `DATA_QUALITY_STATUS`, `VERIFICATION_MESSAGE`) and a longitudinal audit log table (`OPPORTUNITY_VERIFICATION_LOG`).
- **`app.py`**: Streamlit view exposing data quality metrics, pass rates, staleness indicators, diagnostic issue lists, and opt-in manual link reachability checks.

---

## 3. Explicit Data Quality & Verification Semantics

OpportunityLens avoids overloading the single database `STATUS` column by strictly separating three distinct dimensions:

```
┌─────────────────────────────────┐
│     Opportunity Entity          │
├─────────────────────────────────┤
│ 1. Lifecycle Status             │ -> OPEN, CLOSING_SOON, EXPIRED, CLOSED, UNKNOWN
│ 2. Verification Status          │ -> VERIFIED, NEEDS_REVIEW, BROKEN_LINK, UNVERIFIABLE, NOT_CHECKED
│ 3. Data Quality Rating          │ -> PASS, WARNING, FAIL
└─────────────────────────────────┘
```

1. **Opportunity Lifecycle Status**:
   - `OPEN`: Application deadline is active and $\ge 8$ days in the future.
   - `CLOSING_SOON`: Application window closes within $\le 7$ days.
   - `EXPIRED`: Application deadline has passed according to UTC calendar date.
   - `CLOSED`: Explicitly marked closed/archived by official source (distinct from inferred expiry).
   - `UNKNOWN`: Missing or unparseable deadline.
2. **Source Verification Status**:
   - `VERIFIED`: Confirmed directly against primary official source evidence.
   - `NEEDS_REVIEW`: Flagged for review or unverified.
   - `BROKEN_LINK`: Source URL returns HTTP 404, DNS error, or connection failure.
   - `UNVERIFIABLE`: Source blocked by rate limits (HTTP 429), access controls (HTTP 403), or TLS errors.
   - `NOT_CHECKED`: Link check was not executed (offline mode).
3. **Data Quality Rating**:
   - `PASS`: Clean record with zero blocking schema errors or warnings.
   - `WARNING`: Minor non-blocking data quality issues (e.g. brief description, unverified staleness).
   - `FAIL`: Severe blocking errors (e.g. missing title, missing organization, invalid URL, duplicate ID).

### Critical Integrity Principle
> **HTTP 200 Reachability $\neq$ Opportunity Legitimacy**: A successful HTTP 200 response confirms that a web server answered the request. It does **not** prove that an opportunity is legitimate, accredited, or that the application window is currently active. OpportunityLens explicitly badges reachable links as `NEEDS_REVIEW` until primary content evidence is verified.

---

## 4. SSRF Defense & Link Checker Architecture

To prevent Server-Side Request Forgery (SSRF), `SafeSourceChecker` enforces multi-stage defense-in-depth:

1. **Syntax Pre-Check**: Requires explicit `http://` or `https://` schemes; rejects `file://`, `ftp://`, or `javascript:`.
2. **Explicit Localhost Blocking**: Blocks `localhost`, `localhost.localdomain`, and `broadcasthost`.
3. **DNS IP Resolution & Range Validation**: Resolves hostnames before initiating connections and validates destination IPs against forbidden CIDR ranges:
   - `127.0.0.0/8`, `::1` (IPv4/IPv6 Loopback)
   - `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7` (Private subnets)
   - `169.254.0.0/16`, `fe80::/10` (Link-local & AWS/GCP/Azure Metadata endpoints `169.254.169.254`)
   - `224.0.0.0/4`, `ff00::/8` (Multicast addresses)
4. **Redirect Destination Re-Validation**: If an HTTP redirect occurs (e.g. 301/302), the target location URL is parsed and re-evaluated against all SSRF rules before being followed.
5. **Fail-Closed Execution**: If DNS resolution fails, or if destination IP is private, the request is immediately aborted with `UNSAFE_REDIRECT` or `INVALID_OR_FORBIDDEN_URL`.

---

## 5. Security & Isolation Principles

1. **Zero Committed Secrets**: Sensitive database credentials and API keys reside exclusively in `.env`, strictly ignored by `.gitignore`.
2. **Read-Only Database Auditing**: Phase 5 audit operations against Snowflake are strictly read-only (`SELECT`) using parameterized queries; no automated data mutations or schema changes are performed.
3. **Network Isolation by Default**: All automated tests and CLI default invocations execute with network disabled (`network_enabled=False`), requiring explicit user opt-in (`--check-urls`).
4. **Defensive Defaults**: The platform operates with 114 passing automated tests without requiring live network access or Snowflake connectivity.

---

## 3. Matching & Eligibility Engine Design

### 6-Factor Deterministic Compatibility Scoring

The scoring engine produces an explainable, reproducible score between 0.0 and 100.0:

| Factor | Weight | Scoring Logic |
| :--- | :--- | :--- |
| **Education Level** | 25% | 1.0 for exact level match; 0.8 for "All Levels"; 0.0 for explicit conflict (e.g. undergraduate applying for PhD). |
| **Field of Study** | 20% | 1.0 for exact/stem match; 0.7 for related technical domain; 0.5 when student has not specified a major. |
| **Skills Alignment** | 20% | Proportional match based on overlapping technical and academic keywords (Python, SQL, ML, etc.). |
| **Category Preference** | 15% | 1.0 if opportunity category matches student's preferred categories; 0.6 when no preference set. |
| **Location Match** | 10% | 1.0 for matching Nigerian state, nationwide programs, or remote offerings; 0.3 for out-of-state programs. |
| **Delivery Mode** | 10% | 1.0 if opportunity matches preferred mode (remote/on-site/hybrid) or if student has no preference. |

### Conservative 4-State Eligibility Model

Eligibility verification prioritizes correctness and evidence over high relevance scores:

1. **`LIKELY_ELIGIBLE`**: All explicitly stated requirements (education level, CGPA, department, location) are satisfied with confirmed evidence.
2. **`POSSIBLY_ELIGIBLE`**: Primary criteria are met, but secondary or optional requirements exist that require student verification (e.g., department approval or missing CGPA).
3. **`LIKELY_NOT_ELIGIBLE`**: Student profile directly contradicts an explicit requirement (e.g., student CGPA is 2.8 but minimum is 3.5; or student is in secondary school but program requires university undergraduates). **A high match score never overrides a disqualifying outcome.**
4. **`INSUFFICIENT_INFORMATION`**: Opportunity listing lacks documented requirements (e.g., "Check official portal").

---

## 4. Grounded AI Inference & Prompt Security

### Prompt Injection Defense
Language models must never treat opportunity descriptions or student input as executable instructions. OpportunityLens implements defense-in-depth:
1. **Explicit System Instructions**: The model is instructed to act strictly as a grounded summarizer and synthesizer.
2. **Untrusted Evidence Boundary**: All opportunity records and student notes are wrapped inside explicit XML tags:
   ```xml
   <retrieved_opportunity_evidence>
   ...
   </retrieved_opportunity_evidence>
   ```
3. **Ground-Truth Score and URL Enforcement**: When the model returns structured JSON, OpportunityLens enforces the deterministic match score, verified URL, deadline, and eligibility outcome from the database. Even if a language model attempts to hallucinate a higher score or modify a URL, the application overwrites it with verified ground truth.
4. **Deterministic Fallback**: If the external AI service times out, hits rate limits, returns malformed text, or lacks credentials, the system immediately synthesizes an explanation from the deterministic rule engine.

---

## 5. Security & Isolation Principles

1. **Zero Committed Secrets**: All sensitive connection parameters (`SNOWFLAKE_PASSWORD`, `HF_API_KEY`) reside in `.env`, strictly excluded by `.gitignore`.
2. **Zero Leakage Error Sanitization**: All external API exceptions are stripped of tokens, query parameters, and URLs before being logged or displayed to users.
3. **Client-Side Session State for Student Profiles**: Student background, CGPA, and goals are retained strictly in Streamlit memory (`st.session_state`) and are never written to Snowflake tables.
4. **Defensive Defaults**: The application runs completely offline with 71 passing automated tests without requiring external credentials.

---

## 3. Data Schema Design

The Phase 1 in-memory schema is structured to map directly to the target Snowflake table (`OPPORTUNITIES`) in Phase 2:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `opportunity_id` | `VARCHAR(64)` | Unique identifier (e.g., `DEMO-SCH-001`, transitioning to `OPP-2026-XXXX`). |
| `title` | `VARCHAR(255)` | Official title of the opportunity. |
| `category` | `VARCHAR(64)` | One of: `Scholarships`, `Internships`, `Tech Training`, `Hackathons`, `Entry-Level Jobs`. |
| `organization` | `VARCHAR(255)` | Sponsoring company, institution, or NGO. |
| `description` | `TEXT` | Concise summary of the offering and benefits. |
| `eligibility` | `TEXT` | Specific academic, geographic, or experience prerequisites. |
| `education_level`| `VARCHAR(128)` | Target educational standing (Undergraduate, Postgraduate, etc.). |
| `location` | `VARCHAR(128)` | City, state, or remote/hybrid classification in Nigeria. |
| `deadline` | `DATE` | Application closing date (ISO-8601: `YYYY-MM-DD`). |
| `source_url` | `VARCHAR(512)` | Official application link or verified source listing. |
| `verified_at` | `TIMESTAMP` | Timestamp when the opportunity was verified. |
| `status` | `VARCHAR(32)` | Application lifecycle: `Open`, `Closing Soon`, `Closed`. |
| `is_sample_data` | `BOOLEAN` | Explicit flag preventing fictional records from being misrepresented. |

---

## 4. Planned Integrations

### Phase 2: Snowflake Integration (Completed)
- Connected using `snowflake-connector-python` with `DictCursor`.
- Implemented `src/db.py` to query `OPPORTUNITYLENS_DB.APP.OPPORTUNITIES`.
- Integrated cached data loading (`@st.cache_data(ttl=300)`) in `app.py` with refresh controls and error sanitization.
- Derived application status dynamically from deadlines and separated it from the database verification status.
- Added empty-state handling distinguishing successful queries returning zero rows from connection failures.

### Phase 3: Real Opportunity Data & Snowflake CoCo Analytics (Completed)
- Built automated ingestion pipeline (`src/ingestion/`) with data validation, category/date normalization, and deduplication.
- Seeded Snowflake with 13 genuine opportunities from authoritative Nigerian institutions (NITDA, PTDF, MTN Foundation, TotalEnergies, Federal Ministry of Education, etc.).
- Implemented idempotent Snowflake `MERGE` logic ensuring repeated ingestion updates existing records without duplication.
- Formulated and documented 7 analytical queries with **Snowflake CoCo (Cortex Code)** in `docs/snowflake_coco_workflow.md` and `sql/04_coco_queries.sql`.
- Enhanced Streamlit dashboard with live interactive charts, location distribution, upcoming deadline tables, and data freshness metrics.

### Phase 4: Open-Weight AI Assistant (Completed)
- Integrated open-weight model (`meta-llama/Llama-3.2-3B-Instruct`) hosted via **Hugging Face Inference Providers**.
- Implemented structured JSON outputs, prompt injection defenses, untrusted evidence boundaries, and deterministic fallbacks.

### Phase 5: Data Quality, Freshness & Automated Verification (Completed)
- Separated lifecycle status (`OPEN`, `CLOSING_SOON`, `EXPIRED`, `CLOSED`), verification status (`VERIFIED`, `NEEDS_REVIEW`, `BROKEN_LINK`), and data quality rating (`PASS`, `WARNING`, `FAIL`).
- Built safe, SSRF-defended link reachability checker (`src/quality/source_checker.py`).
- Implemented read-only parameterized Snowflake quality audits and automated CLI/UI reporting.

### Phase 6: Production Readiness, Observability & Operational Monitoring (Completed)
- Built multi-component health diagnostics (`src/monitoring/health.py`) with standardized states (`HEALTHY`, `DEGRADED`, `UNAVAILABLE`, `NOT_CHECKED`).
- Implemented reusable operational audit runner (`src/quality/runner.py`) with PID concurrency locking (`.audit_runner.lock`) and deterministic exit codes (0, 1, 2, 3).
- Added structured operational telemetry and secret sanitization (`src/monitoring/logging.py`).
- Created isolated alert notification interface (`src/monitoring/notifications.py`).
- Configured automated GitHub Actions CI workflow (`.github/workflows/ci.yml`).
- Added operations and scheduling guide (`docs/operations.md`).

---

## 5. Security & Isolation Principles

1. **Zero Committed Secrets**: All sensitive connection parameters reside in `.env`, which is strictly ignored by `.gitignore`.
2. **Defensive Defaults**: In the absence of credentials, the platform operates in a zero-network preview mode without throwing unhandled exceptions.
3. **Data Transparency**: All unverified or fictional data is explicitly badged to maintain trust with students and evaluators.
4. **Secret Sanitization**: Operational logs and notification payloads automatically scrub API keys, tokens, authorization headers, and database passwords.
5. **Concurrency Safety**: PID-based file locking prevents overlapping cron or CI audit executions.
