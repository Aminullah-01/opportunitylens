# OpportunityLens 🎯

> **Find opportunities. Understand your chances. Take your next step.**

OpportunityLens is an open-source, AI-powered opportunity discovery platform designed for Nigerian students and early-career talents. It aggregates accredited scholarships, tech internships, developer bootcamps, hackathons, and entry-level positions into a clean, searchable interface.

This project is built for the **Hacktoberfest Hack Day Gombe** competition under the category:
**Best Open-Source AI Project with Snowflake**.

---

## 📌 Current Capabilities (Phase 6: Production Readiness, Observability & Operational Monitoring)

- **System Health & Readiness Diagnostics:** Modular component health evaluation (`src/monitoring/health.py`) assessing runtime readiness, Snowflake presence, AI inference status, storage permissions, and quality subsystem availability with standardized states (`HEALTHY`, `DEGRADED`, `UNAVAILABLE`, `NOT_CHECKED`).
- **Health Diagnostics CLI:** Fast offline diagnostics via `python -m src.monitoring.cli --health` with formatted tables and machine-readable JSON output (`--json`).
- **Operational Audit Runner:** Reusable pipeline runner (`src/quality/runner.py`) suitable for automated cron/CI execution with PID-based concurrency locking (`.audit_runner.lock`), deterministic exit codes (0, 1, 2, 3), and timestamped JSON/CSV report persistence.
- **Structured Operational Telemetry & Secret Redaction:** Structured logger (`src/monitoring/logging.py`) recording UTC timestamps, execution durations, records processed, and issue counts while aggressively redacting API keys, tokens, authorization headers, and credentials.
- **Isolated Notification Interface:** Alert dispatcher (`src/monitoring/notifications.py`) triggering configurable warnings for blocking data errors, stale data surges, broken URL clusters, or pipeline execution failures without requiring external dependencies or credentials.
- **Operator Diagnostics via CLI:** Live component states, audit results, and reports stay available through the monitoring and quality CLIs and logs, keeping the public Streamlit interface focused on opportunity discovery.
- **Continuous Integration Pipeline:** Automated GitHub Actions workflow (`.github/workflows/ci.yml`) verifying test suites, application imports, and offline health checks on Python 3.12.
- **Comprehensive Data Quality Auditing:** Dedicated engine (`src/quality/validator.py`) executing automated checks for missing/whitespace titles, placeholder organizations, malformed categories, incomplete descriptions, vague eligibility, duplicate IDs, duplicate content, and future timestamps.
- **Safe, SSRF-Defended Source Link Checking:** Reusable network link checker (`src/quality/source_checker.py`) protected against Server-Side Request Forgery (SSRF) blocking loopback, private subnets, cloud metadata (`169.254.169.254`), and multicast.
- **AI-Powered Opportunity Matching:** Intelligent discovery engine evaluating student profiles against Snowflake opportunities using multi-factor deterministic scoring, evidence-based eligibility rules, and open-weight model guidance.
- **Comprehensive Automated Test Suite:** Fully offline automated tests running without external network or Snowflake credentials.

---

## 🛠️ Technology Stack

- **Python 3.12+**
- **Streamlit** (User Interface)
- **Pandas** (Data manipulation and preview analytics)
- **python-dotenv** (Secure environment configuration)
- **Pytest** (Automated testing of business logic)
- **Snowflake Python Connector** *(Reserved for Phase 2)*
- **OpenAI Python SDK / Hugging Face Inference Providers** *(Reserved for Phase 4)*

---

## 🚀 Setup & Installation (Ubuntu / Linux)

### 1. Prerequisites

Ensure you have Python 3.12 installed on your Ubuntu/Debian system:

```bash
python3 --version
```

If `python3-venv` or `virtualenv` is not yet installed:
```bash
# Option A: If you have sudo access:
sudo apt update && sudo apt install -y python3.12-venv python3-pip

# Option B: If you do NOT have sudo access (avoids externally managed environment error):
python3 -m pip install --user --break-system-packages virtualenv
```

### 2. Clone the Repository

```bash
git clone https://github.com/your-username/opportunitylens.git
cd opportunitylens
```

### 3. Create and Activate a Virtual Environment

```bash
# If python3.12-venv is installed via apt:
python3 -m venv .venv

# Or using virtualenv (recommended if apt install is not available):
python3 -m virtualenv .venv

# Activate the virtual environment:
source .venv/bin/activate
```

### 4. Install Dependencies

Install the core dependencies:

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Copy the provided template:

```bash
cp .env.example .env
```

In Phase 1, the default values in `.env.example` allow the application to run completely in offline preview mode without external credentials.

---

## 🖥️ Running the Application

Launch the Streamlit development server:

```bash
streamlit run app.py
```

The application will be accessible at:
- Local URL: `http://localhost:8501`
- Network URL: Displayed in the terminal

---

## 📥 Real Opportunity Data Ingestion Architecture

OpportunityLens aggregates genuine, source-backed opportunities directly from legitimate public platforms using a modular source-adapter architecture (`src/ingestion/sources/`).

### 1. Ingestion Hierarchy & Access Policies
OpportunityLens prioritizes data sources in strict accordance with open data ethics:
1. **Official Structured Data & APIs:** Extracts Schema.org `JobPosting` JSON-LD published directly by verified government platforms (e.g. `jobs.leep.gov.ng`).
2. **Official Guidelines & Portals:** Extracts published guidelines and scheme circulars (e.g. `scholarship.ptdf.gov.ng/guidelines`).
3. **SSRF-Defended & Rate-Limited Network Access:** Outbound requests strictly enforce Server-Side Request Forgery (SSRF) defense (blocking loopback, private subnets, cloud metadata `169.254.169.254`, and multicast) with polite inter-request delay (`0.5s`) and bounded timeouts.
4. **No Unauthenticated Scraping of Gated/Anti-Bot Portals:** Platforms requiring login credentials or that prohibit automated extraction in their Terms of Service (e.g. LinkedIn redirects) are documented and safely disabled.

### 2. Registered Source Adapters

| Source ID | Source Name | Target Portal | Status | Ingestion Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| `leep_jobs` | LEEP Jobs | `jobs.leep.gov.ng/jobs` | **ENABLED** | Discovers job links, extracts official Schema.org `JobPosting` JSON-LD (title, org, deadline `validThrough`, location, identifier). |
| `ptdf_scholarships` | Petroleum Technology Development Fund | `scholarship.ptdf.gov.ng/guidelines` | **ENABLED** | Harvests In-Country Scholarship Schemes (ISS) for Undergraduate, MSc, and PhD STEM awards with exact criteria. |
| `nelex_jobs` | National Electronic Labour Exchange | `nelex.gov.ng/` | **ENABLED** | Harvests approved government job listings, qualifications, and closing deadlines. |
| `airtel_careers` | Airtel Nigeria Careers | `airtel.com.ng/ng/about/careers` | **DISABLED** | Third-party LinkedIn redirect requires auth; automated scraping prohibited by ToS. |
| `fed_min_education` | Federal Ministry of Education | `scholarship.education.gov.ng` | **DISABLED** | Homepage currently a minimal landing placeholder (1.8KB) with no open public opportunity catalogue. |
| `ysi_innovation` | Youth & Students in Innovation | `ysi.scienceandtech.gov.ng` | **DISABLED** | Policy overview platform; no active machine-readable hackathon catalogue published. |

### 3. Ingestion Command-Line Interface

Inspect all registered sources and their operational status:
```bash
python -m src.ingestion.cli --list-sources
```

Execute a safe dry-run across all enabled real-data sources (zero database mutations):
```bash
python -m src.ingestion.cli --all-enabled --dry-run
```

Collect from a specific source with a record limit:
```bash
python -m src.ingestion.cli --source leep_jobs --limit 5 --dry-run
python -m src.ingestion.cli --source ptdf_scholarships --dry-run
python -m src.ingestion.cli --source nelex_jobs --limit 5 --dry-run
```

Collect real records and export them to a local JSON file:
```bash
python -m src.ingestion.cli --all-enabled --dry-run --output data/real_opportunities.json
```

Execute live ingestion into Snowflake (`OPPORTUNITYLENS_DB.APP.OPPORTUNITIES`):
```bash
python -m src.ingestion.cli --all-enabled
```
*Note: The pipeline executes an idempotent SQL `MERGE`. Running ingestion repeatedly updates changed fields without creating duplicates.*

Run ingestion completely offline (guarantees zero network outbound calls):
```bash
python -m src.ingestion.cli --all-enabled --no-network
```

Legacy file ingestion (backward-compatible):
```bash
python -m src.ingestion.cli --input-file data/raw_opportunities.json --dry-run
```

---

## 🔒 Production vs. Demo Mode Isolation

- **Production Mode (Default):** The application reads real opportunities directly from Snowflake table `OPPORTUNITYLENS_DB.APP.OPPORTUNITIES`.
- **Zero Silent Fallback:** If the Snowflake connection fails, OpportunityLens shows a clear service-unavailable message. If the table is empty, it shows a friendly empty state. It **never silently substitutes fake records** in production mode.
- **Explicit Demo Mode:** Fictional sample records (`src/demo_data.py`) are only loaded when `OPPORTUNITYLENS_DEMO_MODE=true` is set or the `?demo=true` URL parameter is used. A persistent banner labels the data as fictional.
- **Honest Verification & Deadlines:**
  - A reachable URL (HTTP 200) does not imply an opportunity is verified.
  - If a deadline is not officially published or has expired, it is recorded honestly as `null` / unknown. Deadlines are never invented.
  - If eligibility is unspecified, OpportunityLens flags it as `"Check official requirements"` rather than assuming universal eligibility.


---

## ❄️ Snowflake CoCo (Cortex Code) Analytics

Analytical SQL queries used for data exploration and reporting were developed and refined using **Snowflake CoCo** in the Snowsight worksheet interface:
- **Queries:** `sql/04_coco_queries.sql`
- **Interactive Walkthrough & Findings:** `docs/snowflake_coco_workflow.md`
- **Exploration Prompts:** Category distributions, application deadline lifecycle analysis, 7-day closing window audits, missing eligibility checks, source domain analysis, data freshness tracking, and duplicate detection.

---

## 🛡️ Running Data Quality & Verification Audits

OpportunityLens provides an automated data quality and verification engine (`src/quality/`) that runs both offline (zero network) and with opt-in live link reachability checking.

### 1. Run Offline Data Quality Audit via CLI
Audit local raw opportunity files or Snowflake in safe read-only dry-run mode:
```bash
# Audit raw opportunities data file
python -m src.quality.cli --source file --input-file data/raw_opportunities.json --dry-run

# Audit active Snowflake OPPORTUNITIES table
python -m src.quality.cli --source snowflake --dry-run

# Export structured JSON or CSV audit report
python -m src.quality.cli --source file --output audit_report.json --format json
python -m src.quality.cli --source file --output audit_report.csv --format csv
```

### 2. Run Safe Source Link Verification (Opt-in)
Execute live HTTP reachability checks protected by SSRF defenses and rate limits:
```bash
python -m src.quality.cli --source file --check-urls --stale-days 30
```
*Note: Link checks strictly block internal and private addresses (`127.0.0.1`, `10.0.0.0/8`, `192.168.0.0/16`, `169.254.169.254`). An HTTP 200 response confirms server reachability, not that an application window is open or legitimate.*

---

## 🧪 Running Automated Tests

Run the full test suite using `pytest`:

```bash
python -m pytest -v
```

All **180 automated tests** across 23 test modules run completely offline without external network access or Snowflake credentials:
- **`tests/test_source_adapters.py`** (9 tests): Real source adapter parsing (LEEP Schema.org JSON-LD, PTDF In-Country guidelines, NELEX job extraction), SSRF network defense, rate limiting, and disabled adapter policy enforcement.
- **`tests/test_source_cli.py`** (7 tests): Multi-source ingestion CLI, `--list-sources`, dry-run mode, JSON file export (`--output`), cross-source deduplication, and production isolation.
- **`tests/test_ui_rendering.py`** (11 tests): XSS sanitization, safe URL filtering (`http://` and `https://` only), unindented markdown card rendering, and filter derivations.
- **`tests/test_freshness.py`** (11 tests): Deadline lifecycle evaluation (open, closing soon, expired, closed, unknown), UTC timezone consistency, stale verification tracking (>30d), and future timestamp anomaly detection.
- **`tests/test_source_checker.py`** (9 tests): SSRF IP blocking (loopback, private subnets, cloud metadata `169.254.169.254`), redirect revalidation, HTTP status mapping (200, 404, 403, 429, 500), timeout, connection failure, and offline mode.
- **`tests/test_quality_validator.py`** (12 tests): Hard errors (missing title, missing org, invalid URL, invalid category, empty description) vs warnings (short description, vague eligibility), future verification dates, contradictions, and duplicate detection.
- **`tests/test_quality_pipeline.py`** (4 tests): Full pipeline orchestration, summary metric computations, empty datasets, JSON serialization, and CSV export.
- **`tests/test_quality_snowflake.py`** (3 tests): Parameterized read-only SQL queries, filter parameterization, connection safety, and error handling.
- **`tests/test_quality_cli.py`** (4 tests): CLI arguments, dry-run mode, JSON/CSV exports, and missing file handling.
- **`tests/test_profile.py`** (8 tests): Student profile constraints, validation rules, and skill normalization.
- **`tests/test_scorer.py`** (6 tests): Deterministic scoring weights (100%), score bounds [0, 100], and stable tie-breaking.
- **`tests/test_eligibility.py`** (7 tests): 4-state conservative eligibility engine, CGPA threshold regex parsing, and property alias consistency.
- **`tests/test_search.py`** (6 tests): Natural-language query parsing and search filtering.
- **`tests/test_ai_client.py`** (7 tests): Hugging Face client resilience, missing key handling, timeout and rate limit sanitization.
- **`tests/test_explanations.py`** (6 tests): Deterministic fallback, structured AI JSON parsing, and ground truth score/URL enforcement.
- **`tests/test_ingestion.py`** (12 tests): Ingestion schema validation, date parsing, deduplication, and mock Snowflake `MERGE`.
- **`tests/test_demo_data.py`** (11 tests): Demo dataset schema integrity, status filtering, category extraction, and UI filter logic.
- **`tests/test_snowflake_integration.py`** (9 tests): Application status derivation, safe date rendering, and connection state simulation.


---

## 🤖 Running the AI Matching Assistant

OpportunityLens supports two operational modes:

### Mode 1: Deterministic Explanation Mode (Default, Zero-Credentials)
If `HF_API_KEY` is not set in `.env`, the system automatically activates the **Deterministic Rule Engine**. It executes the 6-factor compatibility scorer and evidence-based eligibility audits, synthesizing structured, grounded advice directly from verified Snowflake records with zero external API calls.

### Mode 2: Neural Open-Weight Model Mode
To enable neural explanations generated by an eligible open-weight model:
1. Obtain a free API key from [Hugging Face](https://huggingface.co/settings/tokens).
2. Configure your `.env` file:
   ```env
   HF_API_KEY=hf_your_actual_token_here
   AI_MODEL_NAME=meta-llama/Llama-3.2-3B-Instruct
   AI_PROVIDER=huggingface
   ```
3. Restart the Streamlit dashboard:
   ```bash
   streamlit run app.py
   ```
4. Match cards will display grounded neural explanations and a short match summary. If the external provider experiences network latency, rate limits, or malformed JSON, OpportunityLens instantly and transparently falls back to the deterministic engine without crashing.

---

## 🗺️ Project Roadmap & Hackathon Plan

- [x] **Phase 1: Project Foundation** *(Completed)*
  - Streamlit UI explorer and responsive cards.
  - Testable filtering and search engine.
  - Safe configuration management and documentation.
- [x] **Phase 2: Snowflake Integration** *(Completed)*
  - Connect `snowflake-connector-python` using `src/db.py`.
  - Cache opportunity records with safe error handling and refresh controls.
  - Derive application status from deadlines and separate from verification status.
  - Handle empty Snowflake database (`OPPORTUNITYLENS_DB.APP.OPPORTUNITIES`) gracefully.
- [x] **Phase 3: Real Opportunity Data & Snowflake CoCo Analytics** *(Completed)*
  - Ingest 13 genuine opportunities from authoritative Nigerian institutions into Snowflake.
  - Build reproducible, idempotent ingestion pipeline (`src/ingestion/`).
  - Develop analytical SQL queries with Snowflake CoCo (`sql/04_coco_queries.sql`, `docs/snowflake_coco_workflow.md`).
  - Analyze live data with Snowflake CoCo SQL (categories, locations, upcoming deadlines, data freshness).
- [x] **Phase 4: AI-Powered Opportunity Matching** *(Completed)*
  - Interactive student profile configuration in session state.
  - Deterministic 6-factor scoring engine with configurable weights.
  - Evidence-based eligibility assessment engine with 4 strict outcomes.
  - Open-weight model guidance (`meta-llama/Llama-3.2-3B-Instruct`) via Hugging Face Inference Providers.
  - Prompt-injection defense, untrusted evidence boundary markers, and JSON schema enforcement.
  - Seamless deterministic fallback when unconfigured or offline.
- [x] **Phase 5: Data Quality, Freshness & Automated Verification** *(Completed)*
  - Automated data quality auditing & integrity engine (`src/quality/validator.py`).
  - Explicit separation: Lifecycle (`OPEN`/`EXPIRED`/`CLOSED`/`UNKNOWN`), Verification (`VERIFIED`/`NEEDS_REVIEW`/`BROKEN_LINK`), and Quality (`PASS`/`WARNING`/`FAIL`).
  - Deterministic deadline and freshness evaluation with configurable staleness thresholds (`src/quality/freshness.py`).
  - Safe source link checking with SSRF protection (`src/quality/source_checker.py`).
  - Read-only parameterized Snowflake audit queries (`src/quality/snowflake_audit.py`).
  - Quality CLI with dry-run and JSON/CSV reports (`src/quality/cli.py`).
  - Quality audit CLI and scheduled runner (`src/quality/`) with operator-facing reports.
- [x] **Phase 6: Production Readiness, Observability & Operational Monitoring** *(Completed)*
  - Component health diagnostics with standardized states (`HEALTHY`, `DEGRADED`, `UNAVAILABLE`, `NOT_CHECKED`) in `src/monitoring/health.py`.
  - Machine-readable health CLI via `python -m src.monitoring.cli --health --json`.
  - Reusable operational audit runner with PID concurrency locking (`src/quality/runner.py`).
  - Deterministic process exit codes (0: success, 1: execution failure, 2: blocking errors, 3: warnings).
  - Structured logging telemetry and aggressive secret redaction (`src/monitoring/logging.py`).
  - Isolated alert notification interface (`src/monitoring/notifications.py`).
  - Automated GitHub Actions CI workflow (`.github/workflows/ci.yml`).
  - Operations and scheduling guide (`docs/operations.md`).

---

## 📁 Repository Structure

```
opportunitylens/
├── .github/
│   └── workflows/
│       └── ci.yml                    # Automated offline CI workflow
├── app.py                            # Streamlit web application entry point (Phase 6)
├── requirements.txt                  # Project dependencies
├── .env.example                      # Template environment variables (no secrets)
├── .gitignore                        # Git ignore rules for venv, secrets, and caches
├── README.md                         # Project documentation and setup instructions
├── LICENSE                           # MIT License
├── data/
│   └── raw_opportunities.json        # Genuine opportunity records collected from public sources
├── sql/
│   ├── 01_schema.sql                 # Table DDL and documentation
│   ├── 02_data_quality.sql           # Data quality audit and verification queries
│   ├── 03_analytics_queries.sql      # Analytical queries and cross-tabulations
│   ├── 04_coco_queries.sql           # Queries formulated/refined via Snowflake CoCo
│   └── 05_phase5_verification_schema.sql # Phase 5 optional migration script
├── src/
│   ├── __init__.py                   # Package initializer
│   ├── analytics.py                  # Analytics computation and summary engine
│   ├── config.py                     # Environment configuration with python-dotenv
│   ├── db.py                         # Snowflake connector data access layer
│   ├── demo_data.py                  # Fictional demo records and testable filter logic
│   ├── utils.py                      # Pure helper utilities (URL/date/category/metrics)
│   ├── monitoring/                   # Phase 6: Observability, health & logging package
│   │   ├── __init__.py               # Monitoring package exports
│   │   ├── cli.py                    # Health check CLI entry point
│   │   ├── health.py                 # Multi-component health & readiness diagnostic engine
│   │   ├── logging.py                # Structured operational logger & secret sanitizer
│   │   └── notifications.py          # Isolated notification channels & alert dispatcher
│   ├── matching/                     # Phase 4: Deterministic matching & eligibility package
│   │   ├── __init__.py               # Matching package exports
│   │   ├── models.py                 # Dataclasses (StudentProfile, MatchResult, EligibilityAssessment)
│   │   ├── profile.py                # Profile validation and token normalization
│   │   ├── scorer.py                 # Deterministic 6-factor scoring and ranking engine
│   │   ├── eligibility.py            # Evidence-based conservative eligibility audit engine
│   │   ├── search.py                 # Natural-language query parsing and search filter
│   │   └── service.py                # Matching orchestrator linking search, profile, and scoring
│   ├── ai/                           # Phase 4: Grounded AI inference & explanation package
│   │   ├── __init__.py               # AI package exports
│   │   ├── client.py                 # Hugging Face Inference Providers client with sanitization
│   │   ├── prompts.py                # System prompts and bounded untrusted evidence builders
│   │   ├── schemas.py                # Structured output schema (ExplanationResponse, ExplanationItem)
│   │   └── explanation.py            # Grounded explanation service with deterministic fallback
│   ├── quality/                      # Phase 5 & 6: Data quality, freshness & verification package
│   │   ├── __init__.py               # Quality package exports
│   │   ├── models.py                 # Data models (QualityIssue, RecordAuditResult, DataQualityReport)
│   │   ├── validator.py              # Record & batch validation and contradiction auditing
│   │   ├── freshness.py              # Deadline lifecycle & verification freshness evaluator
│   │   ├── source_checker.py         # SSRF-protected safe HTTP link reachability checker
│   │   ├── snowflake_audit.py        # Read-only parameterized Snowflake audit queries
│   │   ├── pipeline.py               # Pipeline orchestrator and report generator
│   │   ├── runner.py                 # Phase 6: Operational scheduled runner with process lock
│   │   └── cli.py                    # Standalone CLI runner (--source, --dry-run, --check-urls)
│   └── ingestion/                    # Reproducible ingestion and validation pipeline
│       ├── __init__.py               # Ingestion package root
│       ├── cli.py                    # Standalone CLI runner (--dry-run, --input-file)
│       ├── models.py                 # Dataclasses and report data structures
│       ├── pipeline.py               # Pipeline runner, file loaders, Snowflake MERGE
│       └── validator.py              # Record validation and category/date normalizers
├── tests/
│   ├── test_ai_client.py             # Pytest suite for Hugging Face client resilience
│   ├── test_audit_runner.py          # Pytest suite for Phase 6 operational audit runner & lock
│   ├── test_demo_data.py             # Pytest suite for demo data and filters
│   ├── test_eligibility.py           # Pytest suite for 4-state eligibility engine
│   ├── test_explanations.py          # Pytest suite for AI and deterministic explanation engines
│   ├── test_fresh_imports.py         # Pytest suite for clean imports in fresh processes
│   ├── test_freshness.py             # Pytest suite for deadline and freshness logic
│   ├── test_health.py                # Pytest suite for Phase 6 health states and diagnostics
│   ├── test_ingestion.py             # Pytest suite for validation, deduplication, and mock MERGE
│   ├── test_monitoring_logging.py    # Pytest suite for Phase 6 secret sanitization & logs
│   ├── test_notifications.py         # Pytest suite for Phase 6 alert policies & suppression
│   ├── test_profile.py               # Pytest suite for StudentProfile constraints
│   ├── test_quality_cli.py           # Pytest suite for quality CLI commands
│   ├── test_quality_pipeline.py      # Pytest suite for quality pipeline & serialization
│   ├── test_quality_snowflake.py     # Pytest suite for read-only Snowflake audit queries
│   ├── test_quality_validator.py     # Pytest suite for data quality & contradiction rules
│   ├── test_scorer.py                # Pytest suite for deterministic scoring and ranking
│   ├── test_search.py                # Pytest suite for natural language query parser
│   ├── test_snowflake_integration.py # Pytest suite for Snowflake logic, dates, and URLs
│   └── test_source_checker.py        # Pytest suite for SSRF defense and link checker
└── docs/
    ├── architecture.md               # Detailed system architecture and roadmap
    ├── operations.md                 # Phase 6: Operations, health checks, cron, and logging
    └── snowflake_coco_workflow.md    # Snowflake CoCo prompts, SQL, and factual findings
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
