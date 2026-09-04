-- ============================================================================
-- EPIP M16 — UNITY CATALOG RBAC
-- ============================================================================
-- RBAC decides whether a principal can access an object.
-- ABAC later restricts rows/values visible through granted access.
-- ============================================================================

-- PLATFORM ADMINS
GRANT USE CATALOG ON CATALOG payments_dev TO `epip-platform-admins`;
GRANT MANAGE ON CATALOG payments_dev TO `epip-platform-admins`;
GRANT APPLY TAG ON CATALOG payments_dev TO `epip-platform-admins`;

GRANT USE CATALOG ON CATALOG payments_prod TO `epip-platform-admins`;
GRANT MANAGE ON CATALOG payments_prod TO `epip-platform-admins`;

-- DATA ENGINEERS
GRANT USE CATALOG ON CATALOG payments_dev TO `epip-data-engineers`;
GRANT USE SCHEMA ON SCHEMA payments_dev.ingestion TO `epip-data-engineers`;
GRANT USE SCHEMA ON SCHEMA payments_dev.bronze TO `epip-data-engineers`;
GRANT USE SCHEMA ON SCHEMA payments_dev.silver TO `epip-data-engineers`;
GRANT USE SCHEMA ON SCHEMA payments_dev.gold TO `epip-data-engineers`;
GRANT SELECT ON SCHEMA payments_dev.ingestion TO `epip-data-engineers`;
GRANT SELECT ON SCHEMA payments_dev.bronze TO `epip-data-engineers`;
GRANT SELECT ON SCHEMA payments_dev.silver TO `epip-data-engineers`;
GRANT SELECT ON SCHEMA payments_dev.gold TO `epip-data-engineers`;
GRANT CREATE TABLE ON SCHEMA payments_dev.silver TO `epip-data-engineers`;
GRANT CREATE TABLE ON SCHEMA payments_dev.gold TO `epip-data-engineers`;

-- ML ENGINEERS
GRANT USE CATALOG ON CATALOG payments_dev TO `epip-ml-engineers`;
GRANT USE SCHEMA ON SCHEMA payments_dev.silver TO `epip-ml-engineers`;
GRANT USE SCHEMA ON SCHEMA payments_dev.gold TO `epip-ml-engineers`;
GRANT USE SCHEMA ON SCHEMA payments_dev.features TO `epip-ml-engineers`;
GRANT USE SCHEMA ON SCHEMA payments_dev.ml TO `epip-ml-engineers`;
GRANT USE SCHEMA ON SCHEMA payments_dev.models TO `epip-ml-engineers`;
GRANT SELECT ON SCHEMA payments_dev.silver TO `epip-ml-engineers`;
GRANT SELECT ON SCHEMA payments_dev.gold TO `epip-ml-engineers`;
GRANT SELECT ON SCHEMA payments_dev.features TO `epip-ml-engineers`;
GRANT SELECT ON SCHEMA payments_dev.ml TO `epip-ml-engineers`;
GRANT EXECUTE ON FUNCTION payments_dev.models.fraud_detection_model TO `epip-ml-engineers`;

-- FRAUD ANALYSTS
GRANT USE CATALOG ON CATALOG payments_dev TO `epip-fraud-analysts`;
GRANT USE SCHEMA ON SCHEMA payments_dev.gold TO `epip-fraud-analysts`;
GRANT USE SCHEMA ON SCHEMA payments_dev.analytics TO `epip-fraud-analysts`;
GRANT USE SCHEMA ON SCHEMA payments_dev.silver TO `epip-fraud-analysts`;
GRANT SELECT ON SCHEMA payments_dev.gold TO `epip-fraud-analysts`;
GRANT SELECT ON SCHEMA payments_dev.analytics TO `epip-fraud-analysts`;
GRANT SELECT ON TABLE payments_dev.silver.customers_current TO `epip-fraud-analysts`;

-- AU FRAUD ANALYSTS
-- Explicit grants make nested group membership optional.
GRANT USE CATALOG ON CATALOG payments_dev TO `epip-fraud-analysts-au`;
GRANT USE SCHEMA ON SCHEMA payments_dev.gold TO `epip-fraud-analysts-au`;
GRANT USE SCHEMA ON SCHEMA payments_dev.analytics TO `epip-fraud-analysts-au`;
GRANT USE SCHEMA ON SCHEMA payments_dev.silver TO `epip-fraud-analysts-au`;
GRANT SELECT ON SCHEMA payments_dev.gold TO `epip-fraud-analysts-au`;
GRANT SELECT ON SCHEMA payments_dev.analytics TO `epip-fraud-analysts-au`;
GRANT SELECT ON TABLE payments_dev.silver.customers_current TO `epip-fraud-analysts-au`;

-- BI CONSUMERS — DEV
GRANT USE CATALOG ON CATALOG payments_dev TO `epip-bi-consumers`;
GRANT USE SCHEMA ON SCHEMA payments_dev.gold TO `epip-bi-consumers`;
GRANT USE SCHEMA ON SCHEMA payments_dev.analytics TO `epip-bi-consumers`;
GRANT SELECT ON SCHEMA payments_dev.gold TO `epip-bi-consumers`;
GRANT SELECT ON SCHEMA payments_dev.analytics TO `epip-bi-consumers`;

-- BI CONSUMERS — PROD
GRANT USE CATALOG ON CATALOG payments_prod TO `epip-bi-consumers`;
GRANT USE SCHEMA ON SCHEMA payments_prod.gold TO `epip-bi-consumers`;
GRANT SELECT ON SCHEMA payments_prod.gold TO `epip-bi-consumers`;
