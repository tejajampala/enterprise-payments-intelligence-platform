-- ============================================================================
-- EPIP M16 — GOVERNANCE VALIDATION
-- ============================================================================

-- 1. GOVERNED TAG DEFINITIONS
SELECT
    account_id,
    id,
    tag_key,
    change_time
FROM system.tags.governed_tags
WHERE deleted_at IS NULL
  AND tag_key IN ('epip_classification', 'epip_pii', 'epip_region_key')
ORDER BY tag_key;

-- 2. TABLE-LEVEL CLASSIFICATION
SELECT
    catalog_name,
    schema_name,
    table_name,
    tag_name,
    tag_value
FROM system.information_schema.table_tags
WHERE catalog_name = 'payments_dev'
  AND schema_name = 'silver'
  AND table_name = 'customers_current'
ORDER BY tag_name;

-- 3. COLUMN-LEVEL CLASSIFICATION
SELECT
    catalog_name,
    schema_name,
    table_name,
    column_name,
    tag_name,
    tag_value
FROM system.information_schema.column_tags
WHERE catalog_name = 'payments_dev'
  AND schema_name = 'silver'
  AND table_name = 'customers_current'
ORDER BY column_name, tag_name;

-- 4. CLASSIFICATION COVERAGE
SELECT
    column_name,
    MAX(CASE
        WHEN tag_name = 'epip_classification'
         AND tag_value = 'restricted'
        THEN 1 ELSE 0 END) AS has_restricted_classification,
    MAX(CASE WHEN tag_name = 'epip_pii' THEN 1 ELSE 0 END) AS has_pii_category,
    MAX(CASE WHEN tag_name = 'epip_region_key' THEN 1 ELSE 0 END) AS has_region_key
FROM system.information_schema.column_tags
WHERE catalog_name = 'payments_dev'
  AND schema_name = 'silver'
  AND table_name = 'customers_current'
GROUP BY column_name
ORDER BY column_name;

-- 5. DEVELOPMENT RBAC
SHOW GRANTS ON CATALOG payments_dev;
SHOW GRANTS ON SCHEMA payments_dev.silver;
SHOW GRANTS ON TABLE payments_dev.silver.customers_current;

-- 6. PRODUCTION ISOLATION
SHOW GRANTS ON CATALOG payments_prod;

-- 7. EFFECTIVE ABAC
SHOW EFFECTIVE POLICIES
ON TABLE payments_dev.silver.customers_current;

-- 8. PRIVILEGED QUERY
-- Run as epip-platform-admins or epip-data-engineers.
SELECT
    customer_id,
    first_name,
    last_name,
    date_of_birth,
    email,
    phone,
    address_line_1,
    city,
    state,
    postcode,
    country
FROM payments_dev.silver.customers_current
LIMIT 20;

-- 9. RESTRICTED FRAUD ANALYST
-- Run the same query as a user ONLY in epip-fraud-analysts.
-- Expected: names/phone/address masked, email domain retained, DOB reduced to year.

-- 10. AU FRAUD ANALYST
-- Run as a user ONLY in epip-fraud-analysts-au.
SELECT DISTINCT country
FROM payments_dev.silver.customers_current
ORDER BY country;
-- Expected: AU only.
