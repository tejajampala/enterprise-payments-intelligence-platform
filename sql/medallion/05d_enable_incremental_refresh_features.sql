-- ============================================================================
-- Enterprise Payments Intelligence Platform
-- Milestone 5 / Step 5D
--
-- Enable Delta table features used by downstream materialized views.
--
-- Row Tracking:
--   Provides stable row IDs and row commit versions.
--
-- Change Data Feed:
--   Exposes inserts, updates and deletes between Delta table versions and
--   improves the opportunity for downstream materialized views to refresh
--   incrementally.
--
-- These features do NOT implement business CDC semantics.
-- AUTO CDC / SCD Type 1 / SCD Type 2 are implemented in Milestone 6.
-- ============================================================================


-- ============================================================================
-- Customer snapshot
-- ============================================================================

ALTER TABLE payments_dev.ingestion.customers_snapshot
SET TBLPROPERTIES (
    'delta.enableRowTracking' = 'true',
    'delta.enableChangeDataFeed' = 'true'
);


-- ============================================================================
-- Account snapshot
-- ============================================================================

ALTER TABLE payments_dev.ingestion.accounts_snapshot
SET TBLPROPERTIES (
    'delta.enableRowTracking' = 'true',
    'delta.enableChangeDataFeed' = 'true'
);


-- ============================================================================
-- Merchant snapshot
-- ============================================================================

ALTER TABLE payments_dev.ingestion.merchants_snapshot
SET TBLPROPERTIES (
    'delta.enableRowTracking' = 'true',
    'delta.enableChangeDataFeed' = 'true'
);


-- ============================================================================
-- Fraud-case snapshot
-- ============================================================================

ALTER TABLE payments_dev.ingestion.fraud_cases_snapshot
SET TBLPROPERTIES (
    'delta.enableRowTracking' = 'true',
    'delta.enableChangeDataFeed' = 'true'
);