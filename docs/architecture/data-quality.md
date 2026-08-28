# Data Quality Architecture

## Purpose

The Enterprise Payments Intelligence Platform applies Lakeflow expectations
between standardized Silver datasets and downstream trusted datasets.

The objective is to prevent malformed business records from contaminating
enrichment, Gold analytics, machine learning, and AI workloads while preserving
invalid data for investigation and reprocessing.

---

## Quality Flow

```text
Standardized Silver
        |
        v
Private DQ Classification
Lakeflow Expectations
        |
   +----+----+
   |         |
   v         v
Validated  Quarantine
   |
   v
Downstream processing
```

---

## Data Quality Policies

| Policy | Lakeflow API | EPIP Usage |
|---|---|---|
| Warn | `dp.expect` / `dp.expect_all` | Measure quality and retain records |
| Drop | `dp.expect_or_drop` | Reserved for safely discardable records |
| Fail | `dp.expect_or_fail` | Reserved for critical pipeline invariants |
| Quarantine | `expect_all` + explicit routing | Primary EPIP invalid-record strategy |

Payment records are not silently discarded.

Invalid records are routed to quarantine tables containing:

```text
dq_failed_rules
is_quarantined
dq_status
dq_checked_at
```

---

## Payment Events

Source:

```text
payment_events_standardized
```

Outputs:

```text
payment_events_validated
payment_events_quarantine
```

Row-level rules validate:

- required business identifiers
- event timestamp
- transaction timestamp
- positive sequence number
- positive amount
- valid currency format
- payment-event type
- channel
- payment method
- transaction status
- country code
- Bronze JSON parsing
- Kafka lineage

Duplicate, late, and out-of-order handling is intentionally not part of 6A.

Those trust concerns are implemented in Milestone 6B.

---

## Payment Transactions

Source:

```text
payment_transactions
```

Outputs:

```text
payment_transactions_validated
payment_transactions_quarantine
```

Validated transactions become the input to:

```text
payment_transactions_enriched
```

This ensures invalid payment facts do not propagate into Gold.

---

## Reference Dimensions

The current Milestone 5 snapshot materialized views use warning expectations:

```text
customers_current
accounts_current
merchants_current
fraud_cases_current
```

The expectations establish a quality baseline without changing current
snapshot semantics.

Milestone 6C and 6D introduce CDC-specific validation before AUTO CDC and
SCD processing.

---

## Expectations and Quarantine

Expectations evaluate each configured rule and publish pass/fail metrics into
the Lakeflow pipeline event log.

The quarantine classifier also computes which exact rules failed for each row.

Example:

```text
transaction_id = NULL
amount         = -50

dq_status =
QUARANTINED

dq_failed_rules =
[
  transaction_id_present,
  amount_positive
]
```

This preserves evidence for debugging and controlled reprocessing.

---

## Event Log Monitoring

Lakeflow pipeline expectation metrics are available from the pipeline event log.

Metrics include:

```text
passed_records
failed_records
dropped_records
```

These metrics will later support:

- operational dashboards
- quality trend monitoring
- alerts
- SLA/SLO reporting

---

## Trust Levels

The Silver layer now contains explicit trust stages:

```text
STANDARDIZED
    |
    v
VALIDATED
    |
    v
Milestone 6B
DEDUPLICATED / EVENT-TIME TRUSTED
```

`payment_events_validated` means that every individual row satisfies the
configured record-level rules.

It does not mean that the event has been deduplicated or event-time ordered.

---

## Future Milestone 6 Work

### 6B

Adds:

- duplicate-event handling
- event-time watermarking
- late-event policy
- out-of-order handling

### 6C / 6D

Adds:

- CDC ingestion
- CDC-specific data-quality checks
- AUTO CDC
- SCD Type 1
- SCD Type 2
- delete semantics
- change sequencing