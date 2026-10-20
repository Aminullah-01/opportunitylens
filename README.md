# OpportunityLens 🎯

> **Find opportunities. Understand your chances. Take your next step.**

OpportunityLens is an open-source, AI-powered opportunity discovery platform designed for Nigerian students and early-career talents. It aggregates accredited scholarships, tech internships, developer bootcamps, hackathons, and entry-level positions into a clean, searchable interface.

This project is built for the **Hacktoberfest Hack Day Gombe** competition under the category:
**Best Open-Source AI Project with Snowflake**.

---

## 📌 Phase 1 Capabilities

In **Phase 1: Project Foundation**, we focus on building a robust, maintainable architecture, a responsive user interface, and an automated test suite before integrating external cloud services:

- **Branded Interface:** Professional blue-and-white visual identity with responsive typography and accessible contrast.
- **Opportunity Explorer:** Real-time keyword search and category filtering across scholarships, internships, training programs, hackathons, and entry-level roles.
- **Detailed Opportunity Cards:** Display of key metadata including organization, location, eligibility requirements, application deadlines, and direct source links.
- **Dashboard Metrics:** Aggregate counts displaying total records across opportunity types (clearly badged as preview figures).
- **AI Assistant Placeholder:** Clean preview interface explaining upcoming eligibility matching and grounded recommendations in Phase 4.
- **Snowflake Analytics Placeholder:** Dedicated section demonstrating upcoming aggregation charts and data pipeline roadmaps.
- **Fictional Demo Dataset:** Clearly marked sample records representing realistic opportunities in Nigeria without presenting fabricated data as real.
- **Automated Tests:** Comprehensive Pytest suite validating schema definitions, filtering business logic, and configuration loading.

> [!WARNING]
> **Data Transparency Notice:** All opportunity records and statistics currently shown in Phase 1 are **fictional sample examples** created solely for user interface evaluation and automated testing. Live Snowflake database integration and live AI inference are implemented in subsequent phases.

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

- [x] **Phase 1: Project Foundation** *(Current)*
  - Streamlit UI explorer and responsive cards.
  - Testable filtering and search engine.
  - Safe configuration management and documentation.
- [ ] **Phase 2: Snowflake Connection & Open Dataset**
  - Connect `snowflake-connector-python`.
  - Ingest and host an open, freely accessible dataset of educational and tech opportunities in Nigeria.
- [ ] **Phase 3: Snowflake CoCo SQL Pipeline & Analytics**
  - Utilize Snowflake CoCo to write, optimize, and test SQL queries.
  - Build automated aggregation views for deadline tracking and regional distribution.
- [ ] **Phase 4: Open-Weight AI Assistant**
  - Integrate an eligible open-weight model (`meta-llama/Llama-3.2-3B-Instruct`) via Hugging Face Inference Providers.
  - Provide personalized eligibility scoring and actionable advice grounded on Snowflake data.

---

## 📁 Repository Structure

```
opportunitylens/
├── app.py                   # Streamlit web application entry point
├── requirements.txt         # Project dependencies
├── .env.example             # Template environment variables (no secrets)
├── .gitignore               # Git ignore rules for venv, secrets, and caches
├── README.md                # Project documentation and setup instructions
├── LICENSE                  # MIT License
├── src/
│   ├── __init__.py          # Package initializer
│   ├── config.py            # Environment configuration with python-dotenv
│   └── demo_data.py         # Fictional demo records and testable filter logic
├── tests/
│   └── test_demo_data.py    # Pytest test suite for data and filters
└── docs/
    └── architecture.md      # Detailed system architecture and roadmap
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
