# ADR 0004 — Data Trust and AUTO CDC Strategy

## Status

Accepted

## Context

The payments platform must distinguish between:

- malformed records
- duplicate physical event deliveries
- late events
- out-of-order event delivery
- mutable master-data changes
- historical business state

A single generic Silver table cannot correctly represent all these semantics.

## Decision

The platform uses layered trust processing.

### Row-level quality

Lakeflow expectations validate standardized records.

Invalid records are preserved in quarantine rather than silently discarded.

### Streaming events

Payment events are deduplicated using `event_id` with watermark-aware streaming
state.

Business lateness and streaming watermark policy remain separate concepts.

Out-of-order events are audited but are not automatically discarded.

### Mutable master data

Customer, account, and merchant changes use Lakeflow AUTO CDC.

Business keys are:

- `customer_id`
- `account_id`
- `merchant_id`

`record_version` is the authoritative sequence.

`is_deleted` provides delete semantics.

### Current and historical state

AUTO CDC maintains both:

- SCD Type 1 current-state tables
- SCD Type 2 historical tables

Current-state datasets are used for operational enrichment.

Historical datasets preserve temporal lineage for future analytics, machine
learning, and point-in-time processing.

## Consequences

Benefits:

- deterministic handling of out-of-order CDC
- explicit business history
- auditable invalid records
- bounded streaming state
- protection against duplicate Kafka delivery
- clear separation between standardized and trusted data

Trade-offs:

- additional Silver datasets
- stateful streaming operations require checkpoint/state management
- current-state joins can intentionally lose dimension matches after deletes
- SCD2 history increases storage requirements

## Alternatives Rejected

### Arrival-order CDC

Rejected because physical arrival order is not guaranteed to represent logical
business order.

### SCD1 only

Rejected because historical customer/account/merchant state is required for
future analytical and ML use cases.

### Drop invalid records

Rejected because payment-platform defects require auditability and possible
reprocessing.

### Deduplicate using transaction_id

Rejected because one transaction legitimately produces multiple lifecycle
events.