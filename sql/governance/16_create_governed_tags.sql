CREATE GOVERNED TAG epip_classification
DESCRIPTION 'EPIP enterprise information classification'
VALUES (
    'public',
    'internal',
    'confidential',
    'restricted'
);


CREATE GOVERNED TAG epip_pii
DESCRIPTION 'EPIP PII category'
VALUES (
    'name',
    'date_of_birth',
    'email',
    'phone',
    'address',
    'network_identifier'
);


CREATE GOVERNED TAG epip_region_key
DESCRIPTION 'Column used as a jurisdictional row-access key'
VALUES (
    'country'
);