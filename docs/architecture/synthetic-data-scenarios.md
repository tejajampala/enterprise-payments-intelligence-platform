# Synthetic Data Scenarios

## Purpose

The Enterprise Payments Intelligence Platform maintains a strict separation between:

1. clean canonical synthetic data
2. controlled data-quality and change scenarios

The clean generator always produces valid domain objects.

A separate scenario layer introduces known defects and lifecycle conditions for testing
Databricks ingestion, data quality, CDC, SCD Type 2, and streaming behaviour.

---

## Architecture

```text
Canonical Domain Models
        |
        v
Clean Synthetic Generator
        |
        v
Valid Baseline Dataset
        |
        v
Scenario Injection Layer
        |
        +-- CDC updates
        +-- soft deletes
        +-- duplicate transactions
        +-- malformed raw records
        +-- duplicate events
        +-- out-of-order events
        +-- late-arriving events
        |
        v
Source-System Datasets
```

---

## Customer CDC Scenario

A customer begins as version 1:

```text
customer_id = cust-000001
record_version = 1
city = Melbourne
is_deleted = false
```

The customer moves:

```text
record_version = 2
city = Sydney
is_deleted = false
```

The customer is later deleted:

```text
record_version = 3
city = Sydney
is_deleted = true
```

The synthetic source deliberately delivers:

```text
version 1
version 3
version 2
```

The correct logical order remains:

```text
version 1
version 2
version 3
```

This scenario will later validate AUTO CDC sequencing and SCD Type 2 behaviour.

---

## Account CDC Scenario

An account changes from:

```text
ACTIVE
```

to:

```text
BLOCKED
```

while preserving the same account business key.

---

## Merchant CDC Scenario

A merchant changes to:

```text
risk_rating = HIGH
status = SUSPENDED
```

This provides a meaningful slowly changing dimension example.

---

## Duplicate Transaction Scenario

The same transaction business key is deliberately delivered twice.

Expected future behaviour:

```text
Bronze
    |
    v
duplicate detection
    |
    v
Silver deduplicated transaction
```

---

## Invalid Raw Transaction Scenarios

The scenario layer produces raw records containing:

- missing transaction ID
- negative transaction amount
- invalid currency
- orphan account reference

These payloads deliberately bypass canonical model construction because the domain models
correctly reject invalid business objects.

Future Databricks expectations will determine whether invalid records are dropped,
quarantined, or cause pipeline failure.

---

## Duplicate Streaming Event

The same `event_id` is delivered more than once.

This tests future streaming idempotency and deduplication behaviour.

---

## Out-of-Order Streaming Event

A transaction's lifecycle is logically:

```text
sequence 1 -> AUTHORIZATION
sequence 2 -> SETTLEMENT
```

The stream deliberately delivers:

```text
sequence 2
sequence 1
```

Future processing must use event sequencing rather than assuming arrival order.

---

## Late-Arriving Event

The event has a valid business event timestamp but arrives four hours later.

This will later support testing:

- event-time processing
- watermarks
- late-data handling
- streaming state management

---

## Design Principle

Bad data must not require weakening the canonical business model.

Invalid source records exist before canonical validation.

This preserves:

```text
strict domain contracts
        +
realistic dirty-source behaviour
```

and allows the platform to demonstrate enterprise data-quality controls.