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

## 2. Phase 3 Architecture (Current State)

Phase 3 introduces an automated, reproducible ingestion pipeline, data validation, idempotent Snowflake `MERGE` operations, and live analytical visualizations driven by SQL queries developed with **Snowflake CoCo (Cortex Code)**.

### Component Overview

```mermaid
graph TD
    User([Student / Applicant]) -->|Browser HTTP / WebSocket| StreamlitUI[Streamlit Application app.py]
    
    subgraph Ingestion Pipeline Layer
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

    subgraph Snowflake CoCo Analytical Layer
        SnowsightCoCo[Snowflake CoCo / Cortex Code] -->|SQL Refinement| CoCoQueries[sql/04_coco_queries.sql]
        CoCoQueries -.-> AnalyticsEngine
    end

    subgraph Future Phase 4
        AIProvider[Hugging Face / Open-Weight LLM] -.->|Phase 4 Inference| AIAssistant[Eligibility AI Service]
        AIAssistant -.-> StreamlitUI
    end
```

### Modules in Phase 3

- **`app.py`**: Streamlit frontend implementing the blue-and-white accessible UI, search and filtering controls, live opportunity cards, live metrics, and real-time Snowflake analytics (category, location, deadline timelines, and data freshness).
- **`src/ingestion/`**: Automated data pipeline module containing:
  - `models.py`: Data classes (`NormalizedOpportunity`, `ValidationResult`, `IngestionReport`).
  - `validator.py`: Normalization of categories, dates, datetimes, and URLs, with strict rejection reasons.
  - `pipeline.py`: File loaders, in-batch deduplication, and idempotent Snowflake `MERGE` execution.
  - `cli.py`: Standalone CLI runner with `--input-file` and `--dry-run` modes.
- **`src/analytics.py`**: Pure analytical functions computing category distributions, geographic breakdowns, application lifecycle windows, and verification metrics.
- **`sql/`**: Version-controlled SQL scripts:
  - `01_schema.sql`: Primary table DDL and documentation.
  - `02_data_quality.sql`: Data quality audits and integrity checks.
  - `03_analytics_queries.sql`: Analytical aggregations and lifecycle status.
  - `04_coco_queries.sql`: Analytical queries developed and refined using Snowflake CoCo.
- **`docs/snowflake_coco_workflow.md`**: Comprehensive walkthrough of CoCo prompts, generated SQL, human review, and factual Snowflake findings.

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

### Phase 4: Open-Weight AI Assistant (Upcoming)
- Integrate an eligible open-weight model (such as `meta-llama/Llama-3.2-3B-Instruct`) hosted via **Hugging Face Inference Providers** using the OpenAI-compatible SDK.
- Feed retrieved opportunity criteria into structured prompts so students can receive tailored eligibility checks and actionable application advice without hallucinations.

---

## 5. Security & Isolation Principles

1. **Zero Committed Secrets**: All sensitive connection parameters reside in `.env`, which is strictly ignored by `.gitignore`.
2. **Defensive Defaults**: In the absence of credentials, the platform operates in a zero-network preview mode without throwing unhandled exceptions.
3. **Data Transparency**: All unverified or fictional data is explicitly badged to maintain trust with students and evaluators.
