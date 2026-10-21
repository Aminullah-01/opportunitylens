-- ==============================================================================
-- OpportunityLens — 01_schema.sql
-- Table DDL and Schema Definition for OPPORTUNITIES
-- ==============================================================================

-- Ensure database and schema exist
CREATE DATABASE IF NOT EXISTS OPPORTUNITYLENS_DB;
CREATE SCHEMA IF NOT EXISTS OPPORTUNITYLENS_DB.APP;

USE DATABASE OPPORTUNITYLENS_DB;
USE SCHEMA APP;

-- Primary opportunities table
CREATE TABLE IF NOT EXISTS OPPORTUNITYLENS_DB.APP.OPPORTUNITIES (
    OPPORTUNITY_ID      VARCHAR(64) NOT NULL,
    TITLE               VARCHAR(255) NOT NULL,
    CATEGORY            VARCHAR(64) NOT NULL,
    ORGANIZATION        VARCHAR(255),
    DESCRIPTION         TEXT,
    ELIGIBILITY         TEXT,
    EDUCATION_LEVEL     VARCHAR(128),
    LOCATION            VARCHAR(128),
    DEADLINE            DATE,
    SOURCE_URL          VARCHAR(512),
    VERIFIED_AT         TIMESTAMP_NTZ(9),
    STATUS              VARCHAR(32) DEFAULT 'UNVERIFIED',
    CONSTRAINT PK_OPPORTUNITIES PRIMARY KEY (OPPORTUNITY_ID)
);

-- Documentation on columns
COMMENT ON TABLE OPPORTUNITYLENS_DB.APP.OPPORTUNITIES IS 
    'Central repository of verified scholarships, internships, training, hackathons, and jobs for Nigerian students.';

COMMENT ON COLUMN OPPORTUNITYLENS_DB.APP.OPPORTUNITIES.OPPORTUNITY_ID IS 
    'Unique deterministic identifier (e.g., OPP-NITDA-3MTT-2026).';

COMMENT ON COLUMN OPPORTUNITYLENS_DB.APP.OPPORTUNITIES.STATUS IS 
    'Verification status: VERIFIED, UNVERIFIED, or NEEDS_REVIEW. Distinct from application deadline status.';
