# OpportunityLens 🎯

> **Find opportunities. Understand your chances. Take your next step.**

OpportunityLens is an open-source, AI-powered opportunity discovery platform designed for Nigerian students and early-career talents. It aggregates accredited scholarships, tech internships, developer bootcamps, hackathons, and entry-level positions into a clean, searchable interface.

This project is built for the **Hacktoberfest Hack Day Gombe** competition under the category:
**Best Open-Source AI Project with Snowflake**.

---

## 📌 Current Capabilities (Phase 3: Data Ingestion & Snowflake CoCo Analytics)

- **Automated Ingestion Pipeline:** Comprehensive data pipeline (`src/ingestion/`) with data validation, field normalization, deduplication, and idempotent Snowflake loading.
- **Authoritative Nigerian Opportunity Dataset:** 13 verified listings loaded into `OPPORTUNITYLENS_DB.APP.OPPORTUNITIES` from official public bodies (NITDA 3MTT, PTDF, MTN Foundation, TotalEnergies/NNPC, Federal Ministry of Education, Hacktoberfest Gombe, Interswitch, Shell SPDC, Google/Pluralsight, Flutterwave, Andela, Nigerian Breweries).
- **Snowflake CoCo (Cortex Code) Integration:** Documented interactive workflow and version-controlled SQL queries (`sql/04_coco_queries.sql`, `docs/snowflake_coco_workflow.md`) formulated and refined with Snowflake CoCo in Snowsight worksheets.
- **Live Streamlit Analytics Dashboard:** Interactive charts showing category distributions, geographic breakdowns, application lifecycle windows, upcoming deadline alerts, and data freshness audit timestamps.
- **Idempotent Snowflake `MERGE` Pipeline:** Ensures that running ingestion repeatedly updates records in-place without duplicating rows.
- **Cached Data Access:** Streamlit caching (`@st.cache_data(ttl=300)`) with manual refresh controls to avoid reconnecting on every user interaction.
- **Graceful Empty State Handling:** Accurately distinguishes between a successful connection returning zero rows (`Connected — no opportunity records`) and connection failures (`Unavailable`).
- **Dynamic Application Status:** Automatically derives application lifecycle status (`Open`, `Closing Soon`, `Closed`, `Rolling`) from deadlines, and displays verification status (`✓ Verified` / `Status: NEEDS_REVIEW`) separately.
- **Automated Test Suite:** 32 comprehensive unit tests covering data models, validator rules, deduplication, mock Snowflake `MERGE`, date/status parsing, URL safety, and analytics calculations.

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

## 📥 Running the Ingestion Pipeline

The OpportunityLens ingestion pipeline validates, normalizes, deduplicates, and loads genuine opportunity records into Snowflake using an idempotent `MERGE` operation.

### 1. Test Ingestion with Dry-Run Mode
Validate raw input records and print diagnostic rejection details without connecting or writing to Snowflake:
```bash
python -m src.ingestion.cli --dry-run
```

### 2. Execute Live Ingestion into Snowflake
Load validated records directly into `OPPORTUNITYLENS_DB.APP.OPPORTUNITIES`:
```bash
python -m src.ingestion.cli
```
*Note: The pipeline is idempotent. Rerunning with the same data updates existing rows in-place without generating duplicates.*

---

## ❄️ Snowflake CoCo (Cortex Code) Analytics

Analytical SQL queries powering the dashboard aggregations were developed and refined using **Snowflake CoCo** in the Snowsight worksheet interface:
- **Queries:** `sql/04_coco_queries.sql`
- **Interactive Walkthrough & Findings:** `docs/snowflake_coco_workflow.md`
- **Exploration Prompts:** Category distributions, application deadline lifecycle analysis, 7-day closing window audits, missing eligibility checks, source domain analysis, data freshness tracking, and duplicate detection.

---

## 🧪 Running Automated Tests

Run the test suite using `pytest`:

```bash
python -m pytest -v
```

This validates 32 automated tests covering:
- Ingestion data models and schema validation rules.
- Required-field validation and explicit rejection reporting.
- URL validation and safe clickable link rendering.
- Deadline parsing, date normalization, and application status derivation.
- In-batch and key-based deduplication logic.
- Idempotent Snowflake `MERGE` execution with mocked database connections.
- Analytics aggregations, location breakdowns, and data freshness calculations.
- Configuration safety and demo-data integrity.

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
  - Expose live analytics in Streamlit dashboard (categories, locations, upcoming deadlines, data freshness).
- [ ] **Phase 4: Open-Weight AI Assistant**
  - Integrate an eligible open-weight model (`meta-llama/Llama-3.2-3B-Instruct`) via Hugging Face Inference Providers.
  - Provide personalized eligibility scoring and actionable advice grounded on Snowflake data.

---

## 📁 Repository Structure

```
opportunitylens/
├── app.py                            # Streamlit web application entry point
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
│   └── 04_coco_queries.sql           # Queries formulated/refined via Snowflake CoCo
├── src/
│   ├── __init__.py                   # Package initializer
│   ├── analytics.py                  # Analytics computation and summary engine
│   ├── config.py                     # Environment configuration with python-dotenv
│   ├── db.py                         # Snowflake connector data access layer
│   ├── demo_data.py                  # Fictional demo records and testable filter logic
│   ├── utils.py                      # Pure helper utilities (URL/date/category/metrics)
│   └── ingestion/                    # Reproducible ingestion and validation pipeline
│       ├── __init__.py               # Ingestion package root
│       ├── cli.py                    # Standalone CLI runner (--dry-run, --input-file)
│       ├── models.py                 # Dataclasses and report data structures
│       ├── pipeline.py               # Pipeline runner, file loaders, Snowflake MERGE
│       └── validator.py              # Record validation and category/date normalizers
├── tests/
│   ├── test_demo_data.py             # Pytest test suite for demo data and filters
│   ├── test_snowflake_integration.py # Pytest suite for Snowflake logic, dates, and URLs
│   └── test_ingestion.py             # Pytest suite for validation, deduplication, and mock MERGE
└── docs/
    ├── architecture.md               # Detailed system architecture and roadmap
    └── snowflake_coco_workflow.md    # Snowflake CoCo prompts, SQL, and factual findings
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
