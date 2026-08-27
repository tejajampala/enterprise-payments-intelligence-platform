# ADR 0003 — Lakeflow Dataset and Change Processing Strategy

## Status

Accepted.

## Context

The payments platform contains different data semantics:

- immutable payment events
- append-oriented transaction facts
- mutable customer/account/merchant state
- enrichment joins
- business aggregates

Using the same Lakeflow dataset type for every workload would either create
unnecessary recomputation or incorrect incremental semantics.

## Decision

Use streaming tables for append-oriented facts and events:

- `payment_events_standardized`
- `payment_transactions`

Use materialized views when existing results can change because of joins,
mutable dimensions or aggregation:

- current reference dimensions
- `payment_transactions_enriched`
- Gold business metrics

Enable Delta Row Tracking and Change Data Feed on tables that directly
participate as sources for change-sensitive materialized-view processing.

Do not treat Row Tracking or CDF as business CDC logic.

Use Lakeflow AUTO CDC in Milestone 6 for mutable dimensions where business-key,
sequence, update and delete semantics are required.

## Consequences

### Benefits

- append-only facts avoid unnecessary recomputation
- current-state joins remain correct when dimensions change
- Gold aggregates remain logically consistent
- downstream materialized views have improved opportunities for incremental
  refresh
- CDC/SCD concerns remain clearly separated from semantic transformation

### Trade-offs

- Row Tracking and CDF upgrade Delta table features
- table features must be considered when using external Delta clients
- materialized-view incremental refresh is controlled by Databricks and may
  still choose a full recompute
- current snapshot dimensions remain baseline-only until AUTO CDC is added

## Future

Milestone 6 introduces:

- AUTO CDC
- SCD Type 1
- SCD Type 2
- CDC sequencing
- soft-delete handling
- out-of-order change processing