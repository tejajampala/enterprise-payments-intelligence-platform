-- ============================================================================
-- EPIP M16 — GOVERNED TAG DEFINITIONS
-- ============================================================================
-- CREATE GOVERNED TAG has no IF NOT EXISTS form.
-- Run SHOW GOVERNED TAGS first and create only missing tags.
-- ============================================================================

CREATE GOVERNED TAG epip_classification
DESCRIPTION 'EPIP enterprise sensitivity classification used for discovery, audit, and ABAC policy scope'
VALUES ('public', 'internal', 'confidential', 'restricted');

CREATE GOVERNED TAG epip_pii
DESCRIPTION 'EPIP PII category used to select type-specific column masking policy'
VALUES ('name', 'date_of_birth', 'email', 'phone', 'address', 'network_identifier');

CREATE GOVERNED TAG epip_region_key
DESCRIPTION 'EPIP jurisdictional row-security key'
VALUES ('country');
