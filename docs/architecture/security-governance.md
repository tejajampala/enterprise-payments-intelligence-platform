# EPIP Security and Governance Architecture

## Purpose

Milestone 16 adds enterprise identity, RBAC, governed classification, ABAC masking,
jurisdictional row filtering, environment isolation, and governance evidence.

## Architecture

```text
                         Databricks Account
                                │
                         Account Identities
                                │
           ┌────────────────────┼────────────────────┐
           ▼                    ▼                    ▼
      Human Groups         CI Service SP        Prod Service SP
           │                    │                    │
           └──────────────┬─────┴──────────────┬────┘
                          ▼                    ▼
                  Workspace Access      Workload Identity
                          │                    │
                          └─────────┬──────────┘
                                    ▼
                               Unity Catalog
                                    │
                         ┌──────────┴──────────┐
                         ▼                     ▼
                        RBAC              Governed Tags
                         │                     │
              Can access object?      ┌────────┼────────┐
                                      ▼        ▼        ▼
                           classification     pii   region_key
                                      │        │        │
                                      └────┬───┴───┬────┘
                                           ▼       ▼
                                        Masks   Row Filters
                                           │       │
                                           └───┬───┘
                                               ▼
                                         Governed Data
```

## Identity Model

Human access uses account-level groups:

```text
epip-platform-admins
epip-data-engineers
epip-ml-engineers
epip-fraud-analysts
epip-fraud-analysts-au
epip-bi-consumers
```

Automation uses separate OIDC service principals:

```text
epip-github-actions-ci
epip-github-actions-prod
```

## Three Different Security Layers

### Workspace assignment

Can the identity use the workspace?

### RBAC

Can the identity access the catalog/schema/table/function/model?

### ABAC

If access exists, which rows and values are visible?

```text
Account Group → Workspace → RBAC → ABAC → Visible Data
```

## Governed Tags

### `epip_classification`

Values:

```text
public
internal
confidential
restricted
```

This tag is used for discovery, audit, security inventory, and **ABAC policy scope**.

The initial protected table is tagged:

```text
payments_dev.silver.customers_current
    epip_classification = restricted
```

Policies use:

```sql
WHEN has_tag_value('epip_classification', 'restricted')
```

### `epip_pii`

Values:

```text
name
date_of_birth
email
phone
address
network_identifier
```

This tag selects the mask type.

### `epip_region_key`

Value:

```text
country
```

This tag maps the row-filter UDF to the jurisdiction column.

## Why Classification and PII Are Separate

`restricted` says a field is sensitive, but does not say how to mask it.

| Field | Classification | PII type | Mask |
|---|---|---|---|
| first_name | restricted | name | full mask |
| email | restricted | email | domain only |
| phone | restricted | phone | full mask |
| date_of_birth | restricted | date_of_birth | year only |
| address_line_1 | restricted | address | full mask |

So:

```text
epip_classification → policy scope
epip_pii            → masking behavior
```

## Row Filtering

The AU fraud analyst group is restricted to:

```text
country = AU
```

through:

```text
epip_region_key = country
```

## Environment Isolation

```text
CI SP
  → payments_ci
  → narrow promotion evidence only

Prod SP
  → payments_prod
```

CI/prod service principals are not ABAC mask exceptions. Their isolation is enforced
by RBAC and environment boundaries.

## Governed Tag Administration

Applying a governed tag requires:

```text
APPLY TAG on target object
+
ASSIGN on governed tag
```

Tag assignment must remain a restricted governance capability because changing a
tag can change effective ABAC behavior.

## Completion Criteria

M16 remains **IN PROGRESS** until:

```text
groups assigned
RBAC applied
governed tags created
classification applied
UDFs created
ABAC policies created
effective policies verified
masked-user behavior verified
AU row filtering verified
CI/prod isolation verified
tests passing
docs complete
```
