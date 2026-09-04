-- ============================================================================
-- GROUP / PRIVILEGE VALIDATION
-- ============================================================================

SHOW GRANTS ON CATALOG payments_dev;

SHOW GRANTS ON SCHEMA payments_dev.silver;

SHOW GRANTS ON TABLE payments_dev.silver.customers_current;


-- ============================================================================
-- TAG VALIDATION
-- ============================================================================

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


-- ============================================================================
-- GOVERNED TAG DEFINITIONS
-- ============================================================================

SELECT
    tag_key,
    change_time
FROM system.tags.governed_tags
WHERE deleted_at IS NULL
  AND tag_key LIKE 'epip_%'
ORDER BY tag_key;


-- ============================================================================
-- EFFECTIVE ABAC POLICIES
-- ============================================================================

SHOW EFFECTIVE POLICIES
ON TABLE payments_dev.silver.customers_current;