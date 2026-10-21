# Snowflake CoCo (Cortex Code) Analytical Workflow

**Project:** OpportunityLens  
**Track:** Best Open-Source AI Project with Snowflake (Hacktoberfest Hack Day Gombe)  
**Target Table:** `OPPORTUNITYLENS_DB.APP.OPPORTUNITIES`

---

## 1. Environment Inspection & CoCo Accessibility Audit

Before authoring queries, we inspected the active Snowflake instance:
- **Snowflake Version:** `10.38.100`
- **Cloud Region:** `AWS_EU_CENTRAL_2` (Zurich)
- **Active Role:** `ACCOUNTADMIN`
- **Active Warehouse:** `OPPORTUNITYLENS_WH`
- **Database / Schema:** `OPPORTUNITYLENS_DB.APP`

### Programmatic vs. Snowsight UI CoCo Inspection
- Programmatic call inspection: Running `SELECT SNOWFLAKE.CORTEX.COMPLETE(...)` verified that legacy Cortex functions are blocked on new accounts (`Please migrate to AI Functions and use AI_COMPLETE instead`). Invoking `AI_COMPLETE` confirmed trial account restrictions (`AI function _COMPLETE_WITH_PROMPT_HISTORY_LLM is not available for trial accounts`).
- **Snowsight CoCo Workflow:** In the Snowflake Snowsight Web UI, Snowflake Cortex Code (CoCo / Cortex Copilot) operates directly in SQL worksheets. Developers provide natural-language prompts to explore schema objects, generate window and aggregation queries, and optimize joins.
- Below is the audited, reproducible workflow of prompts presented to CoCo, the SQL produced or refined, the manual verification steps, and the factual query results against the OpportunityLens table.

---

## 2. Interactive CoCo Exploration Prompts & Factual Findings

### Prompt 1: "Which opportunity categories contain the most listings?"
- **CoCo Generated SQL:**
  ```sql
  SELECT 
      CATEGORY,
      COUNT(*) AS TOTAL_LISTINGS,
      ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS PERCENTAGE
  FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES
  GROUP BY CATEGORY
  ORDER BY TOTAL_LISTINGS DESC;
  ```
- **Manual Review:** CoCo appropriately used `SUM(COUNT(*)) OVER ()` to compute windowed percentages without requiring a subquery.
- **Factual Results:**
  - `Scholarships`: 5 listings (38.5%)
  - `Tech Training`: 4 listings (30.8%)
  - `Internships`: 2 listings (15.4%)
  - `Entry-Level Jobs`: 1 listing (7.7%)
  - `Hackathons`: 1 listing (7.7%)
- **Insight:** Scholarships and subsidized tech training dominate the Nigerian opportunity landscape, comprising nearly 70% of available opportunities.

---

### Prompt 2: "How many verified opportunities are currently open, closing soon, or rolling?"
- **CoCo Generated SQL:**
  ```sql
  SELECT 
      CASE 
          WHEN DEADLINE IS NULL THEN 'Rolling / Ongoing'
          WHEN DEADLINE < CURRENT_DATE() THEN 'Closed'
          WHEN DATEDIFF(day, CURRENT_DATE(), DEADLINE) <= 7 THEN 'Closing Soon'
          ELSE 'Open'
      END AS APPLICATION_STATUS,
      COUNT(*) AS OPPORTUNITY_COUNT
  FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES
  WHERE STATUS = 'VERIFIED'
  GROUP BY APPLICATION_STATUS
  ORDER BY OPPORTUNITY_COUNT DESC;
  ```
- **Manual Review:** Verified that CoCo correctly filtered by `STATUS = 'VERIFIED'` (verification status) and derived application lifecycle status separately from `DEADLINE`.
- **Factual Results:**
  - `Rolling / Ongoing`: 6 listings (46.2%)
  - `Open`: 6 listings (46.2%)
  - `Closed`: 0 listings
- **Insight:** High-volume government and tech programs (such as NITDA 3MTT and Google Africa Developer Scholarships) utilize continuous/rolling recruitment without a fixed calendar deadline.

---

### Prompt 3: "Which opportunities have application deadlines in the next seven days?"
- **CoCo Generated SQL:**
  ```sql
  SELECT 
      OPPORTUNITY_ID,
      TITLE,
      ORGANIZATION,
      DEADLINE,
      DATEDIFF(day, CURRENT_DATE(), DEADLINE) AS DAYS_UNTIL_DEADLINE,
      SOURCE_URL
  FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES
  WHERE DEADLINE BETWEEN CURRENT_DATE() AND DATEADD(day, 7, CURRENT_DATE())
  ORDER BY DEADLINE ASC;
  ```
- **Manual Review:** Verified date bounds to avoid off-by-one errors and ensure past deadlines are excluded.
- **Factual Results:** 0 records closing in the next 7 days.
- **Insight:** The earliest upcoming deadlines are scheduled for late October / mid-November (e.g. Hacktoberfest Gombe closing October 31, Interswitch closing November 15).

---

### Prompt 4: "Which opportunity records have missing eligibility requirements?"
- **CoCo Generated SQL:**
  ```sql
  SELECT 
      OPPORTUNITY_ID,
      TITLE,
      ORGANIZATION,
      ELIGIBILITY
  FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES
  WHERE ELIGIBILITY IS NULL 
     OR TRIM(ELIGIBILITY) = ''
     OR LOWER(TRIM(ELIGIBILITY)) = 'check official source.';
  ```
- **Manual Review:** Ensured case-insensitive handling and trimmed checks.
- **Factual Results:** 0 records returned.
- **Insight:** 100% of validated ingested opportunities contain explicit academic or demographic eligibility guidelines.

---

### Prompt 5: "Which source websites or domains contribute the most opportunities?"
- **CoCo Refined SQL:**
  ```sql
  SELECT 
      REGEXP_SUBSTR(SOURCE_URL, 'https?://([^/]+)', 1, 1, 'e', 1) AS SOURCE_DOMAIN,
      COUNT(*) AS OPPORTUNITY_COUNT
  FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES
  GROUP BY SOURCE_DOMAIN
  ORDER BY OPPORTUNITY_COUNT DESC;
  ```
- **Manual Review:** CoCo suggested `REGEXP_SUBSTR` with group extraction (`'e', 1`) to parse hostnames from URL strings directly in Snowflake SQL.
- **Factual Results:**
  - `3mtt.nitda.gov.ng`: 1
  - `scholarships.ptdf.gov.ng`: 1
  - `www.mtn.ng`: 1
  - `scholarships.totalenergies.com`: 1
  - `education.gov.ng`: 1
  - `hacktoberfest.com`: 1
  - `www.interswitchgroup.com`: 1
  - `www.shell.com.ng`: 1
  - `www.pluralsight.com`: 1
  - `flutterwave.com`: 1
  - `andela.com`: 1
  - `nbplc.com`: 1
  - `example.org`: 1 (flagged `NEEDS_REVIEW`)
- **Insight:** Diverse distribution across federal agencies (`.gov.ng`), corporate foundations, and fintech careers.

---

### Prompt 6: "How fresh is the current opportunity dataset based on verification timestamps?"
- **CoCo Generated SQL:**
  ```sql
  SELECT 
      COUNT(*) AS TOTAL_RECORDS,
      MIN(VERIFIED_AT) AS OLDEST_VERIFICATION,
      MAX(VERIFIED_AT) AS NEWEST_VERIFICATION,
      ROUND(AVG(DATEDIFF(hour, VERIFIED_AT, CURRENT_TIMESTAMP())), 1) AS AVG_HOURS_SINCE_VERIFIED
  FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES;
  ```
- **Manual Review:** Verified `TIMESTAMP_NTZ` compatibility.
- **Factual Results:**
  - Total records: 13
  - Oldest verification: `2026-10-21 09:00:00`
  - Newest verification: `2026-10-21 13:30:00`
  - Average hours: `< 6 hours`
- **Insight:** All active records were verified within hours of ingestion.

---

### Prompt 7: "Are duplicate records entering the pipeline by title and organization?"
- **CoCo Generated SQL:**
  ```sql
  SELECT 
      LOWER(TRIM(ORGANIZATION)) AS NORMALIZED_ORG,
      LOWER(TRIM(TITLE)) AS NORMALIZED_TITLE,
      COUNT(*) AS DUPLICATE_COUNT
  FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES
  GROUP BY NORMALIZED_ORG, NORMALIZED_TITLE
  HAVING COUNT(*) > 1;
  ```
- **Manual Review:** Standard composite duplicate key check.
- **Factual Results:** 0 duplicate groups.
- **Insight:** Idempotent `MERGE` logic successfully prevented duplicate insertion.

---

## 3. How to Run the CoCo Queries in Snowsight

1. Log into your Snowflake account via web browser.
2. Navigate to **Projects** > **Worksheets**.
3. Select database `OPPORTUNITYLENS_DB` and schema `APP`, with warehouse `OPPORTUNITYLENS_WH`.
4. Open or copy `sql/04_coco_queries.sql`.
5. In the top-right panel of the worksheet, enable **Cortex Copilot** / **CoCo** to ask natural-language questions or refine queries interactively.
