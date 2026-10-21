-- ==============================================================================
-- OpportunityLens — 04_coco_queries.sql
-- Analytical SQL Queries Formulated and Refined via Snowflake CoCo (Cortex Code)
-- ==============================================================================

USE DATABASE OPPORTUNITYLENS_DB;
USE SCHEMA APP;

-- Prompt 1: "Which opportunity categories contain the most listings?"
-- CoCo formulated: Aggregation on CATEGORY with descending ordering
SELECT 
    CATEGORY,
    COUNT(*) AS TOTAL_LISTINGS,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS PERCENTAGE
FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES
GROUP BY CATEGORY
ORDER BY TOTAL_LISTINGS DESC;

-- Prompt 2: "How many verified opportunities are currently open, closing soon, or rolling?"
-- CoCo formulated: Filter on STATUS = 'VERIFIED' and CASE statement on DEADLINE
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

-- Prompt 3: "Which opportunities have application deadlines in the next seven days?"
-- CoCo formulated: Window query checking current date up to +7 days
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

-- Prompt 4: "Which opportunity records have missing eligibility requirements?"
-- CoCo formulated: Audit for NULL, whitespace-only, or generic fallback strings
SELECT 
    OPPORTUNITY_ID,
    TITLE,
    ORGANIZATION,
    ELIGIBILITY
FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES
WHERE ELIGIBILITY IS NULL 
   OR TRIM(ELIGIBILITY) = ''
   OR LOWER(TRIM(ELIGIBILITY)) = 'check official source.';

-- Prompt 5: "Which source websites or domains contribute the most opportunities?"
-- CoCo refined: Extracted domain name from SOURCE_URL using regex
SELECT 
    REGEXP_SUBSTR(SOURCE_URL, 'https?://([^/]+)', 1, 1, 'e', 1) AS SOURCE_DOMAIN,
    COUNT(*) AS OPPORTUNITY_COUNT
FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES
GROUP BY SOURCE_DOMAIN
ORDER BY OPPORTUNITY_COUNT DESC;

-- Prompt 6: "How fresh is the current opportunity dataset based on verification timestamps?"
-- CoCo formulated: Temporal aggregations on VERIFIED_AT timestamp
SELECT 
    COUNT(*) AS TOTAL_RECORDS,
    MIN(VERIFIED_AT) AS OLDEST_VERIFICATION,
    MAX(VERIFIED_AT) AS NEWEST_VERIFICATION,
    ROUND(AVG(DATEDIFF(hour, VERIFIED_AT, CURRENT_TIMESTAMP())), 1) AS AVG_HOURS_SINCE_VERIFIED
FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES;

-- Prompt 7: "Are duplicate records entering the pipeline by title and organization?"
-- CoCo formulated: Normalized grouping on organization and title having count > 1
SELECT 
    LOWER(TRIM(ORGANIZATION)) AS NORMALIZED_ORG,
    LOWER(TRIM(TITLE)) AS NORMALIZED_TITLE,
    COUNT(*) AS DUPLICATE_COUNT
FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES
GROUP BY NORMALIZED_ORG, NORMALIZED_TITLE
HAVING COUNT(*) > 1;
