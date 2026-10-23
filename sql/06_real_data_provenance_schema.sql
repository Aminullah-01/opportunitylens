-- ==============================================================================
-- OpportunityLens — 06_real_data_provenance_schema.sql
-- Phase 6: Optional Non-Destructive Data Provenance Schema Migration
-- ==============================================================================
--
-- IMPORTANT SAFETY NOTICE:
-- This script is optional, non-destructive, and versioned. Do NOT run this script
-- automatically in production. Database migrations must be reviewed and executed
-- manually by a Snowflake administrator via Snowsight.
--
-- Compatibility:
-- This script preserves all existing columns and records in
-- OPPORTUNITYLENS_DB.APP.OPPORTUNITIES without breaking existing queries from
-- Phases 1–5.
-- ==============================================================================

USE DATABASE OPPORTUNITYLENS_DB;
USE SCHEMA APP;

-- ------------------------------------------------------------------------------
-- External Source Provenance & Lineage Columns on OPPORTUNITIES Table
-- ------------------------------------------------------------------------------

ALTER TABLE OPPORTUNITYLENS_DB.APP.OPPORTUNITIES ADD COLUMN IF NOT EXISTS
    SOURCE_IDENTIFIER       VARCHAR(64);

ALTER TABLE OPPORTUNITYLENS_DB.APP.OPPORTUNITIES ADD COLUMN IF NOT EXISTS
    SOURCE_RECORD_ID        VARCHAR(128);

ALTER TABLE OPPORTUNITYLENS_DB.APP.OPPORTUNITIES ADD COLUMN IF NOT EXISTS
    COLLECTED_AT            TIMESTAMP_NTZ(9);

ALTER TABLE OPPORTUNITYLENS_DB.APP.OPPORTUNITIES ADD COLUMN IF NOT EXISTS
    RAW_METADATA            TEXT;

COMMENT ON COLUMN OPPORTUNITYLENS_DB.APP.OPPORTUNITIES.SOURCE_IDENTIFIER IS
    'Identifier of external source adapter that harvested the record (e.g. leep_jobs, ptdf_scholarships, nelex_jobs).';

COMMENT ON COLUMN OPPORTUNITYLENS_DB.APP.OPPORTUNITIES.SOURCE_RECORD_ID IS
    'Upstream source record ID or slug provided by the external publisher.';

COMMENT ON COLUMN OPPORTUNITYLENS_DB.APP.OPPORTUNITIES.COLLECTED_AT IS
    'UTC timestamp when the opportunity payload was retrieved from the source.';

COMMENT ON COLUMN OPPORTUNITYLENS_DB.APP.OPPORTUNITIES.RAW_METADATA IS
    'Structured source metadata or JSON payload for audit traceability (secrets redacted).';
