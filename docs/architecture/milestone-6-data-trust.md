# Milestone 6 — Enterprise Data Trust, CDC, and SCD Architecture

## Overview

Milestone 6 converts the standardized Medallion architecture from Milestone 5
into a trusted enterprise data-processing architecture.

It introduces four related capabilities:

1. row-level data quality
2. trusted streaming-event processing
3. master-data CDC
4. SCD Type 1 and SCD Type 2 processing

The resulting Silver layer provides governed datasets for Gold analytics,
machine learning, feature engineering, and future AI workloads.

---

## End-to-End Architecture

```text
                         SOURCE SYSTEMS

              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼

      Payment Transactions          Payment Events
          S3 / Delta                  Kafka / MSK
              │                           │
              ▼                           ▼

        Standardized Silver         Bronze Events
              │                           │
              │                           ▼
              │                  Standardized Events
              │                           │
              ▼                           ▼
       Data Quality Gate            Data Quality Gate
              │                           │
        ┌─────┴─────┐               ┌─────┴─────┐
        │           │               │           │
        ▼           ▼               ▼           ▼
   Validated    Quarantine      Validated    Quarantine
        │                           │
        │                           ▼
        │                  Event-Time Trust
        │                           │
        │                    ┌──────┼──────┐
        │                    │      │      │
        │                    ▼      ▼      ▼
        │                  Dedup   Late   Ordering
        │                    │
        │                    ▼
        │            payment_events_trusted
        │
        │
        │               MASTER DATA
        │
        │     ┌──────────────┴──────────────┐
        │     │                             │
        │     ▼                             ▼
        │  Snapshot                      CDC Files
        │     │                             │
        │     │                        Auto Loader
        │     │                             │
        │     └──────────────┬──────────────┘
        │                    ▼
        │                 AUTO CDC
        │            keys + record_version
        │                    │
        │       ┌────────────┴────────────┐
        │       │                         │
        │       ▼                         ▼
        │    SCD Type 1               SCD Type 2
        │   Current State                History
        │
        └───────────────────┐
                            ▼
                payment_transactions_enriched
                            │
                            ▼
                           GOLD
```

---

# 1. Row-Level Data Quality

Payment records are evaluated using reusable Lakeflow expectation rules.

The architecture separates:

```text
STANDARDIZED
     ↓
VALIDATED
```

rather than treating standardization as equivalent to trust.

Invalid records are preserved through explicit quarantine tables.

Examples include:

- missing business identifiers
- negative payment amounts
- malformed currency codes
- invalid status values
- malformed event payloads
- missing Kafka lineage

The quarantine datasets retain:

```text
dq_failed_rules
is_quarantined
dq_status
dq_checked_at
```

Invalid financial records are therefore observable rather than silently lost.

---

# 2. Streaming Event Trust

A valid payment event can still have delivery anomalies.

The streaming trust layer therefore addresses concerns that are independent of
row-level data quality.

## Deduplication

Kafka and other event publishers can provide at-least-once delivery.

The trusted event stream uses:

```python
withWatermark(...)
dropDuplicatesWithinWatermark(["event_id"])
```

`event_id` is the business event identifier.

`transaction_id` is intentionally not used as the deduplication key because a
single transaction can legitimately have multiple lifecycle events.

Example:

```text
transaction
   ├── sequence 1 AUTHORIZATION
   └── sequence 2 SETTLEMENT
```

---

## Business Lateness vs Streaming Watermark

The platform separates two concepts:

```text
Business late threshold = 2 hours
Streaming watermark     = 6 hours
```

A four-hour-late event is therefore:

```text
LATE from a business SLA perspective
but
still eligible for trusted processing
```

This prevents business observability policy from being confused with state
retention policy.

---

## Out-of-Order Events

Lifecycle events can physically arrive out of sequence.

Example:

```text
Physical arrival

sequence 2
sequence 1
```

The lower sequence is recorded as an out-of-order delivery anomaly.

The event is not automatically discarded because the business event itself can
still be valid.

The trusted dataset preserves the event while the exception dataset preserves
the delivery anomaly.

---

# 3. CDC Architecture

Mutable reference data uses a snapshot-plus-CDC pattern.

Entities:

```text
Customer
Account
Merchant
```

Initial source state is hydrated from the PostgreSQL-style snapshot.

Subsequent changes are consumed from append-oriented CDC files using Auto
Loader.

The CDC feed includes:

```text
business key
record_version
source_updated_at
is_deleted
```

---

# 4. AUTO CDC

Lakeflow AUTO CDC applies mutable business changes using:

```text
KEY
+
SEQUENCE
+
DELETE SEMANTICS
```

EPIP uses:

```text
Customer key = customer_id
Account key  = account_id
Merchant key = merchant_id

sequence_by = record_version
```

Physical arrival order is therefore not assumed to be correct.

---

## Out-of-Order CDC Scenario

The controlled customer scenario physically arrives:

```text
version 1
version 3 DELETE
version 2 UPDATE
```

Naive processing by arrival order could incorrectly produce:

```text
DELETE
then
resurrect customer using version 2
```

AUTO CDC instead evaluates the sequence:

```text
version 1
    ↓
version 2
    ↓
version 3 DELETE
```

The final current-state customer is therefore deleted.

This validates one of the primary reasons for using sequence-aware CDC
processing.

---

# 5. SCD Type 1

Current-state targets include:

```text
customers_current
accounts_current
merchants_current
```

These datasets expose only the latest valid business state.

Examples:

```text
Account:
ACTIVE → BLOCKED

Merchant:
LOW risk / ACTIVE
        ↓
HIGH risk / SUSPENDED
```

Consumers that require today's business state use these datasets.

---

# 6. SCD Type 2

Historical targets include:

```text
customer_history
account_history
merchant_history
```

AUTO CDC maintains:

```text
__START_AT
__END_AT
```

which creates temporal business history.

Example:

```text
Account

v1 ACTIVE
__START_AT = 1
__END_AT   = 2

v2 BLOCKED
__START_AT = 2
__END_AT   = NULL
```

This enables historical analytics and point-in-time feature engineering.

---

# 7. Delete Semantics

Deletes are applied through:

```text
is_deleted = true
```

AUTO CDC tombstone retention is configured so that older, late-arriving updates
cannot immediately resurrect recently deleted business records.

---

# 8. Current-State Enrichment

`payment_transactions_enriched` consumes:

```text
payment_transactions_validated
accounts_current
customers_current
merchants_current
fraud_cases_current
```

Customer, account, and merchant dimensions now come from SCD1 AUTO CDC current
state.

Therefore an old transaction can be enriched using the latest current
reference state.

---

# 9. Deleted Dimension Members

A historical transaction can legitimately fail a current-state dimension match.

Example:

```text
Transaction occurred while customer existed
                 ↓
Customer later deleted through CDC
                 ↓
Historical transaction remains
                 ↓
Current customer dimension contains no customer
```

Therefore:

```text
customer_dimension_match = false
```

is not automatically a data-quality failure.

Point-in-time historical enrichment can later use the SCD2 history datasets when
required.

---

# 10. Gold Consistency

Gold datasets remain materialized views because they represent current aggregate
query results.

Final reconciliation verifies:

```text
validated transactions
      =
enriched transactions

enriched transaction count
      =
sum(Gold daily transaction_count)

enriched payment amount
      =
sum(Gold daily total_payment_amount)
```

---

# 11. Trust Layers

The final Medallion trust model is:

```text
BRONZE
Raw physical fidelity

        ↓

SILVER STANDARDIZED
Schema and normalization

        ↓

SILVER VALIDATED
Row-level DQ passed

        ↓

SILVER TRUSTED
Deduplication / CDC / event-time semantics applied

        ↓

GOLD
Business-ready aggregates
```

---

# Milestone 6 Outcomes

Milestone 6 demonstrates:

- Lakeflow expectations
- quarantine design
- streaming deduplication
- event-time watermarking
- late-event classification
- out-of-order event detection
- Auto Loader CDC ingestion
- snapshot hydration
- AUTO CDC
- delete semantics
- out-of-order CDC resolution
- SCD Type 1
- SCD Type 2
- current-state enrichment
- Silver-to-Gold reconciliation

The resulting datasets are ready to support Milestone 7 feature engineering and
Feature Store development.