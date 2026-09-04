-- ============================================================================
-- EPIP M16 — ATTRIBUTE-BASED ACCESS CONTROL
-- ============================================================================
-- epip_classification=restricted scopes the protected table.
-- epip_pii selects the type-specific mask.
-- epip_region_key identifies the row-filter input.
-- ============================================================================

CREATE OR REPLACE POLICY epip_mask_customer_name
ON SCHEMA payments_dev.silver
COMMENT 'Mask direct customer names on restricted tables for non-privileged account users.'
COLUMN MASK payments_dev.governance.mask_string
TO `account users`
EXCEPT `epip-platform-admins`, `epip-data-engineers`
FOR TABLES
WHEN has_tag_value('epip_classification', 'restricted')
MATCH COLUMNS has_tag_value('epip_pii', 'name') AS pii_col
ON COLUMN pii_col;

CREATE OR REPLACE POLICY epip_mask_customer_email
ON SCHEMA payments_dev.silver
COMMENT 'Mask customer email while retaining domain context on restricted tables.'
COLUMN MASK payments_dev.governance.mask_email
TO `account users`
EXCEPT `epip-platform-admins`, `epip-data-engineers`
FOR TABLES
WHEN has_tag_value('epip_classification', 'restricted')
MATCH COLUMNS has_tag_value('epip_pii', 'email') AS pii_col
ON COLUMN pii_col;

CREATE OR REPLACE POLICY epip_mask_customer_phone
ON SCHEMA payments_dev.silver
COMMENT 'Mask customer telephone details on restricted tables.'
COLUMN MASK payments_dev.governance.mask_string
TO `account users`
EXCEPT `epip-platform-admins`, `epip-data-engineers`
FOR TABLES
WHEN has_tag_value('epip_classification', 'restricted')
MATCH COLUMNS has_tag_value('epip_pii', 'phone') AS pii_col
ON COLUMN pii_col;

CREATE OR REPLACE POLICY epip_mask_customer_address
ON SCHEMA payments_dev.silver
COMMENT 'Mask customer address attributes on restricted tables.'
COLUMN MASK payments_dev.governance.mask_string
TO `account users`
EXCEPT `epip-platform-admins`, `epip-data-engineers`
FOR TABLES
WHEN has_tag_value('epip_classification', 'restricted')
MATCH COLUMNS has_tag_value('epip_pii', 'address') AS pii_col
ON COLUMN pii_col;

CREATE OR REPLACE POLICY epip_mask_customer_dob
ON SCHEMA payments_dev.silver
COMMENT 'Reduce exact date-of-birth precision on restricted tables.'
COLUMN MASK payments_dev.governance.mask_date_of_birth
TO `account users`
EXCEPT `epip-platform-admins`, `epip-data-engineers`
FOR TABLES
WHEN has_tag_value('epip_classification', 'restricted')
MATCH COLUMNS has_tag_value('epip_pii', 'date_of_birth') AS pii_col
ON COLUMN pii_col;

CREATE OR REPLACE POLICY epip_au_customer_scope
ON SCHEMA payments_dev.silver
COMMENT 'Restrict AU-scoped fraud analysts to Australian rows on restricted customer tables.'
ROW FILTER payments_dev.governance.allow_au_country
TO `epip-fraud-analysts-au`
FOR TABLES
WHEN has_tag_value('epip_classification', 'restricted')
MATCH COLUMNS has_tag_value('epip_region_key', 'country') AS country_col
USING COLUMNS (country_col);
