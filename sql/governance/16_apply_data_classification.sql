-- ============================================================================
-- EPIP CUSTOMER PII CLASSIFICATION
-- ============================================================================


ALTER STREAMING TABLE payments_dev.silver.customers_current
ALTER COLUMN first_name
SET TAGS (
    'epip_classification' = 'restricted',
    'epip_pii' = 'name'
);


ALTER STREAMING TABLE payments_dev.silver.customers_current
ALTER COLUMN last_name
SET TAGS (
    'epip_classification' = 'restricted',
    'epip_pii' = 'name'
);


ALTER STREAMING TABLE payments_dev.silver.customers_current
ALTER COLUMN date_of_birth
SET TAGS (
    'epip_classification' = 'restricted',
    'epip_pii' = 'date_of_birth'
);


ALTER STREAMING TABLE payments_dev.silver.customers_current
ALTER COLUMN email
SET TAGS (
    'epip_classification' = 'restricted',
    'epip_pii' = 'email'
);


ALTER STREAMING TABLE payments_dev.silver.customers_current
ALTER COLUMN phone
SET TAGS (
    'epip_classification' = 'restricted',
    'epip_pii' = 'phone'
);


ALTER STREAMING TABLE payments_dev.silver.customers_current
ALTER COLUMN address_line_1
SET TAGS (
    'epip_classification' = 'restricted',
    'epip_pii' = 'address'
);


ALTER STREAMING TABLE payments_dev.silver.customers_current
ALTER COLUMN city
SET TAGS (
    'epip_classification' = 'restricted',
    'epip_pii' = 'address'
);


ALTER STREAMING TABLE payments_dev.silver.customers_current
ALTER COLUMN state
SET TAGS (
    'epip_classification' = 'restricted',
    'epip_pii' = 'address'
);


ALTER STREAMING TABLE payments_dev.silver.customers_current
ALTER COLUMN postcode
SET TAGS (
    'epip_classification' = 'restricted',
    'epip_pii' = 'address'
);


ALTER STREAMING TABLE payments_dev.silver.customers_current
ALTER COLUMN country
SET TAGS (
    'epip_classification' = 'restricted',
    'epip_region_key' = 'country'
);