-- ============================================================================
-- NAME
-- ============================================================================

CREATE OR REPLACE POLICY epip_mask_customer_name
ON SCHEMA payments_dev.silver
COMMENT 'Mask direct customer names from non-privileged consumers.'
COLUMN MASK payments_dev.governance.mask_string
TO `account users`
EXCEPT
    `epip-platform-admins`,
    `epip-data-engineers`,
    `epip-github-actions-ci`,
    `epip-github-actions-prod`
FOR TABLES
MATCH COLUMNS
    has_tag_value('epip_pii', 'name') AS pii_col
ON COLUMN pii_col;


-- ============================================================================
-- EMAIL
-- ============================================================================

CREATE OR REPLACE POLICY epip_mask_customer_email
ON SCHEMA payments_dev.silver
COMMENT 'Mask customer email while retaining domain context.'
COLUMN MASK payments_dev.governance.mask_email
TO `account users`
EXCEPT
    `epip-platform-admins`,
    `epip-data-engineers`,
    `epip-github-actions-ci`,
    `epip-github-actions-prod`
FOR TABLES
MATCH COLUMNS
    has_tag_value('epip_pii', 'email') AS pii_col
ON COLUMN pii_col;


-- ============================================================================
-- PHONE
-- ============================================================================

CREATE OR REPLACE POLICY epip_mask_customer_phone
ON SCHEMA payments_dev.silver
COMMENT 'Mask customer telephone details.'
COLUMN MASK payments_dev.governance.mask_string
TO `account users`
EXCEPT
    `epip-platform-admins`,
    `epip-data-engineers`,
    `epip-github-actions-ci`,
    `epip-github-actions-prod`
FOR TABLES
MATCH COLUMNS
    has_tag_value('epip_pii', 'phone') AS pii_col
ON COLUMN pii_col;


-- ============================================================================
-- ADDRESS
-- ============================================================================

CREATE OR REPLACE POLICY epip_mask_customer_address
ON SCHEMA payments_dev.silver
COMMENT 'Mask customer address attributes.'
COLUMN MASK payments_dev.governance.mask_string
TO `account users`
EXCEPT
    `epip-platform-admins`,
    `epip-data-engineers`,
    `epip-github-actions-ci`,
    `epip-github-actions-prod`
FOR TABLES
MATCH COLUMNS
    has_tag_value('epip_pii', 'address') AS pii_col
ON COLUMN pii_col;


-- ============================================================================
-- DATE OF BIRTH
-- ============================================================================

CREATE OR REPLACE POLICY epip_mask_customer_dob
ON SCHEMA payments_dev.silver
COMMENT 'Reduce exact date-of-birth precision for non-privileged users.'
COLUMN MASK payments_dev.governance.mask_date_of_birth
TO `account users`
EXCEPT
    `epip-platform-admins`,
    `epip-data-engineers`,
    `epip-github-actions-ci`,
    `epip-github-actions-prod`
FOR TABLES
MATCH COLUMNS
    has_tag_value('epip_pii', 'date_of_birth') AS pii_col
ON COLUMN pii_col;

CREATE OR REPLACE POLICY epip_au_customer_scope
ON SCHEMA payments_dev.silver
COMMENT 'Restrict AU-scoped fraud analysts to Australian customer rows.'
ROW FILTER payments_dev.governance.allow_au_country
TO `epip-fraud-analysts-au`
FOR TABLES
MATCH COLUMNS
    has_tag_value('epip_region_key', 'country') AS country_col
USING COLUMNS (
    country_col
);