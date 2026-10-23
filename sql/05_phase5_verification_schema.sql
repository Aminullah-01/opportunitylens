-- ==============================================================================
-- OpportunityLens — 05_phase5_verification_schema.sql
-- Phase 5: Optional Non-Destructive Data Quality & Verification Schema Migration
-- ==============================================================================
--
-- IMPORTANT SAFETY NOTICE:
-- This script is optional and versioned. Do NOT run this script automatically
-- in production. Database migrations must be reviewed and executed manually by
-- a Snowflake administrator via Snowsight.
--
-- Compatibility:
-- This script preserves all existing columns and records in
-- OPPORTUNITYLENS_DB.APP.OPPORTUNITIES without breaking existing Phase 1-4 queries.
-- ==============================================================================

USE DATABASE OPPORTUNITYLENS_DB;
USE SCHEMA APP;

-- ------------------------------------------------------------------------------
-- Option 1: In-Place Non-Destructive Metadata Columns on OPPORTUNITIES Table
-- ------------------------------------------------------------------------------
-- Adds explicit audit and freshness tracking columns without altering existing data.

ALTER TABLE OPPORTUNITYLENS_DB.APP.OPPORTUNITIES ADD COLUMN IF NOT EXISTS
    LAST_CHECKED_AT         TIMESTAMP_NTZ(9);

ALTER TABLE OPPORTUNITYLENS_DB.APP.OPPORTUNITIES ADD COLUMN IF NOT EXISTS
    DATA_QUALITY_STATUS     VARCHAR(16) DEFAULT 'PASS';

ALTER TABLE OPPORTUNITYLENS_DB.APP.OPPORTUNITIES ADD COLUMN IF NOT EXISTS
    VERIFICATION_MESSAGE    TEXT;

COMMENT ON COLUMN OPPORTUNITYLENS_DB.APP.OPPORTUNITIES.LAST_CHECKED_AT IS
    'UTC timestamp when the opportunity was last audited for freshness and link validity.';

COMMENT ON COLUMN OPPORTUNITYLENS_DB.APP.OPPORTUNITIES.DATA_QUALITY_STATUS IS
    'Overall data quality score: PASS, WARNING, or FAIL.';

COMMENT ON COLUMN OPPORTUNITYLENS_DB.APP.OPPORTUNITIES.VERIFICATION_MESSAGE IS
    'Detailed audit diagnosis or reason if flagged for review or broken link.';


-- ------------------------------------------------------------------------------
-- Option 2: Dedicated Verification History Log Table (Audit Trail)
-- ------------------------------------------------------------------------------
-- Records individual automated checks over time for longitudinal auditability.

CREATE TABLE IF NOT EXISTS OPPORTUNITYLENS_DB.APP.OPPORTUNITY_VERIFICATION_LOG (
    LOG_ID                  VARCHAR(64) NOT NULL,
    OPPORTUNITY_ID          VARCHAR(64) NOT NULL,
    CHECKED_AT              TIMESTAMP_NTZ(9) NOT NULL,
    VERIFICATION_STATUS     VARCHAR(32) NOT NULL,  -- VERIFIED, NEEDS_REVIEW, BROKEN_LINK, UNVERIFIABLE, NOT_CHECKED
    DATA_QUALITY_STATUS     VARCHAR(16) NOT NULL,  -- PASS, WARNING, FAIL
    HTTP_STATUS             INTEGER,               -- HTTP response code (e.g. 200, 404, 403, 429)
    LATENCY_MS              FLOAT,                 -- Network roundtrip latency in milliseconds
    ERROR_CODE              VARCHAR(64),           -- e.g. HTTP_404_NOT_FOUND, TIMEOUT, SSRF_BLOCKED
    DIAGNOSTIC_MESSAGE      TEXT,                  -- Human-readable explanation
    AUDIT_RUN_BY            VARCHAR(64) DEFAULT 'AUTOMATED_AUDITOR',
    CONSTRAINT PK_VERIFICATION_LOG PRIMARY KEY (LOG_ID),
    CONSTRAINT FK_VERIFICATION_OPP FOREIGN KEY (OPPORTUNITY_ID)
        REFERENCES OPPORTUNITYLENS_DB.APP.OPPORTUNITIES (OPPORTUNITY_ID)
);

COMMENT ON TABLE OPPORTUNITYLENS_DB.APP.OPPORTUNITY_VERIFICATION_LOG IS
    'Append-only historical audit log recording source link checks and data quality scans.';
