# Milestone 16 — Security and Governance Runbook

## 1. Confirm account groups

Verify these account groups exist:

```text
epip-platform-admins
epip-data-engineers
epip-ml-engineers
epip-fraud-analysts
epip-fraud-analysts-au
epip-bi-consumers
```

Do not create duplicate workspace-local groups.

## 2. Assign account groups to the workspace

If the UI does not surface the existing account group, use the supported account
workspace-assignment CLI/API with the actual workspace ID and group ID.

After assignment, confirm the workspace shows:

```text
Source = Account
```

## 3. Apply RBAC

Run:

```text
sql/governance/16_apply_rbac.sql
```

Validate:

```sql
SHOW GRANTS ON CATALOG payments_dev;
SHOW GRANTS ON SCHEMA payments_dev.silver;
SHOW GRANTS ON TABLE payments_dev.silver.customers_current;
SHOW GRANTS ON CATALOG payments_prod;
```

## 4. Create governed tags

First:

```sql
SHOW GOVERNED TAGS;
```

Then create only missing tags with:

```text
sql/governance/16_create_governed_tags.sql
```

Required:

```text
epip_classification
epip_pii
epip_region_key
```

## 5. Restrict governed-tag assignment

Grant the required governed-tag assignment permission to the governance admin role.

Do not broadly grant it to analyst, BI, CI, or production identities.

## 6. Create security UDFs

Run:

```text
sql/governance/16_create_security_functions.sql
```

Expected functions:

```text
mask_string
mask_email
mask_date_of_birth
allow_au_country
```

## 7. Apply classification

Run:

```text
sql/governance/16_apply_data_classification.sql
```

Expected table tag:

```text
customers_current
    epip_classification = restricted
```

Expected column examples:

```text
email
    epip_classification = restricted
    epip_pii = email

country
    epip_classification = restricted
    epip_region_key = country
```

## 8. Create ABAC policies

Run:

```text
sql/governance/16_create_abac_policies.sql
```

Expected:

```text
epip_mask_customer_name
epip_mask_customer_email
epip_mask_customer_phone
epip_mask_customer_address
epip_mask_customer_dob
epip_au_customer_scope
```

## 9. Verify effective policies

```sql
SHOW EFFECTIVE POLICIES
ON TABLE payments_dev.silver.customers_current;
```

Expected: five masks plus one AU row filter.

## 10. Privileged test

As platform admin or data engineer, query the protected customer table.

Expected: original values visible.

## 11. Restricted fraud-analyst test

As a user only in:

```text
epip-fraud-analysts
```

Expected:

```text
name    → masked
email   → masked local part, domain retained
phone   → masked
DOB     → YYYY-01-01
address → masked
country → visible
```

## 12. AU analyst test

As a user only in:

```text
epip-fraud-analysts-au
```

Run:

```sql
SELECT DISTINCT country
FROM payments_dev.silver.customers_current
ORDER BY country;
```

Expected:

```text
AU
```

## 13. Validate environment isolation

Confirm:

```text
CI SP   → no broad payments_prod access
Prod SP → no broad payments_dev access
```

## 14. Run validation SQL

Run:

```text
sql/governance/16_validate_governance.sql
```

Capture evidence for tags, grants, effective policies, masking, and row filtering.

## 15. Run quality gates

```powershell
uv run pytest tests/unit/test_security_governance_contracts.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```

## 16. Definition of done

```text
[ ] groups assigned to workspace
[ ] source verified as Account
[ ] RBAC applied
[ ] governed tags created
[ ] tag assignment restricted
[ ] table classified restricted
[ ] PII columns tagged
[ ] security UDFs created
[ ] ABAC policies created
[ ] effective policies verified
[ ] restricted user sees masks
[ ] AU user sees AU rows only
[ ] CI/prod isolation verified
[ ] tests pass
[ ] docs updated
[ ] PR merged
[ ] post-merge CI/CD green
```

Only then mark M16 COMPLETE.
