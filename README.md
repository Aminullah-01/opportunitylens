# OpportunityLens 🎯

> **Find opportunities. Understand your chances. Take your next step.**

OpportunityLens is an open-source, AI-powered opportunity discovery platform designed for Nigerian students and early-career talents. It aggregates accredited scholarships, tech internships, developer bootcamps, hackathons, and entry-level positions into a clean, searchable interface.

This project is built for the **Hacktoberfest Hack Day Gombe** competition under the category:
**Best Open-Source AI Project with Snowflake**.

---

## 📌 Current Capabilities (Phase 2: Snowflake Integration)

- **Live Snowflake Integration:** Connects directly to Snowflake table `OPPORTUNITYLENS_DB.APP.OPPORTUNITIES` via `src/db.py` using `snowflake-connector-python`.
- **Cached Data Access:** Leverages Streamlit caching (`@st.cache_data(ttl=300)`) with manual refresh controls to avoid reconnecting on each user interaction.
- **Graceful Empty State Handling:** Accurately distinguishes between a successful connection returning zero rows (`Connected — no opportunity records`) and connection failures (`Unavailable`).
- **Dynamic Application Status:** Automatically derives application lifecycle status (`Open`, `Closing Soon`, `Closed`, `Unknown`) from deadlines, and displays verification status (`✓ Verified` / `Status: UNVERIFIED`) separately.
- **Dynamic Category Filtering:** Derives category filter options directly from the active opportunity dataset.
- **Safe Link Handling:** Validates external source links before rendering clickable URLs.
- **Preview Fallback Toggle:** Allows reviewers to preview sample records when the live database contains 0 records.
- **Automated Test Suite:** 20 comprehensive unit tests covering demo data, live Snowflake data structures, date/status parsing, URL validation, and category derivation.

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

## 🧪 Running Automated Tests

Run the test suite using `pytest`:

```bash
pytest -v
```

This tests:
- Data structure and required fields on all demo opportunities.
- Strict `is_sample_data` flags and `DEMO-` prefixing.
- Canonical category and status membership.
- Pure search and category filtering logic outside Streamlit.
- Metric calculation accuracy.
- Configuration loading safety.

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
- [ ] **Phase 3: Real Opportunity Data & Snowflake CoCo Analytics**
  - Ingest public datasets into Snowflake.
  - Utilize Snowflake CoCo to write, optimize, and test SQL queries.
  - Build automated aggregation views for deadline tracking and regional distribution.
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
├── src/
│   ├── __init__.py                   # Package initializer
│   ├── config.py                     # Environment configuration with python-dotenv
│   ├── db.py                         # Snowflake connector data access layer
│   ├── demo_data.py                  # Fictional demo records and testable filter logic
│   └── utils.py                      # Pure helper utilities (URL/date/category/metrics)
├── tests/
│   ├── test_demo_data.py             # Pytest test suite for demo data and filters
│   └── test_snowflake_integration.py # Pytest suite for Snowflake logic, dates, and URLs
└── docs/
    └── architecture.md               # Detailed system architecture and roadmap
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
