# Lakeflow Medallion Architecture

## Purpose

The Enterprise Payments Intelligence Platform uses Bronze, Silver and Gold
layers to progressively transform source-system data into governed,
business-ready data products.

The architecture intentionally uses different Lakeflow dataset types depending
on data semantics rather than making every dataset a streaming table.

---

## Architecture

```text
                         SOURCES

             S3                       MSK
              |                        |
              v                        v

     Batch ingestion                 Bronze
              |                   payment_events
              |                 Streaming Table
              |                        |
              |                        v
              |              payment_events_standardized
              |                 Streaming Table
              |
              v
 payment_transactions_batch_s3
              |
              | readStream
              v
     payment_transactions
       Streaming Table
       Row Tracking ON
       CDF ON
              |
              +--------------------------+
                                         |
Customers snapshot                       |
Accounts snapshot                        |
Merchants snapshot                       |
Fraud cases snapshot                     |
       |                                 |
       v                                 |
Current Dimension MVs                    |
Row Tracking ON                          |
CDF ON                                   |
       |                                 |
       +---------------+-----------------+
                       |
                       v
          payment_transactions_enriched
                Materialized View
                Row Tracking ON
                CDF ON
                       |
                       v
                     Gold
                       |
         +-------------+-------------+
         |             |             |
         v             v             v

       Daily        Merchant       Channel
       Metrics       Metrics        Metrics
          \             |             /
           \            |            /
            +-----------+-----------+
                        |
                        v
                 Fraud Operations
```

---

## Dataset Design

| Dataset | Type | Incremental mechanism | Row Tracking | CDF | AUTO CDC |
|---|---|---|---|---|---|
| Bronze payment events | Streaming table | Kafka/checkpoint | No | No | No |
| Silver payment events | Streaming table | checkpoint | No | No | No |
| Silver payment transactions | Streaming table | checkpoint | Yes | Yes | No |
| Silver current dimensions | Materialized views | MV refresh | Yes | Yes | No |
| Silver enriched transactions | Materialized view | MV refresh | Yes | Yes | No |
| Gold metrics | Materialized views | MV refresh | No currently | No currently | No |
| Mutable dimensions in Milestone 6 | Streaming targets | AUTO CDC | Later | Later | Yes |

---

## Streaming Tables

Streaming tables are used when source records are append-oriented and previously
processed records do not normally need to be recalculated.

Examples:

```text
payment_events_standardized
payment_transactions
```

The primary incremental mechanism is the streaming checkpoint.

Row Tracking and CDF are not what cause `readStream` to process only new rows.

---

## Materialized Views

Materialized views represent the current result of a query.

They are used when previous outputs can change because of:

- dimension updates
- joins
- aggregations
- current-state calculations

Examples:

```text
customers_current
accounts_current
merchants_current
payment_transactions_enriched
daily_payment_metrics
```

Databricks decides whether an eligible materialized view refresh should be
incremental or fully recomputed.

The logical result is identical in either case.

---

## Row Tracking

Row Tracking provides stable Delta row IDs and row commit versions.

It helps Databricks identify changed source rows for operations including some
incremental materialized-view refresh strategies.

Row Tracking does not understand:

```text
customer_id is a business key
version 3 replaces version 2
is_deleted means remove the customer
```

Those are business CDC semantics.

---

## Change Data Feed

CDF exposes row-level changes such as:

```text
INSERT
UPDATE_PREIMAGE
UPDATE_POSTIMAGE
DELETE
```

CDF is useful for:

- incremental downstream ETL
- replication
- audit trails
- cache synchronization
- external-system synchronization
- materialized-view incremental-refresh optimization

CDF is not required merely to process an append-only Kafka or S3 stream.

---

## AUTO CDC

AUTO CDC applies business changes using keys and sequencing.

For example:

```text
customer_id = business key
source_updated_at = sequence
```

AUTO CDC can maintain:

```text
SCD Type 1 current state
SCD Type 2 history
```

AUTO CDC is intentionally deferred to Milestone 6.

Example future architecture:

```text
customer CDC
     |
     v
AUTO CDC
 keys = customer_id
 sequence = source_updated_at
     |
 +---+---+
 |       |
 v       v
SCD1    SCD2
current history
```

---

## Current Snapshot Limitation

Milestone 5 uses one baseline PostgreSQL-style snapshot.

The current dimension MVs therefore provide current state for that baseline.

Repeated full snapshots must not simply be appended indefinitely and assumed
to produce SCD semantics.

Milestone 6 introduces explicit CDC processing and SCD history.

---

## Gold

Gold remains materialized-view based because its purpose is to maintain correct
business aggregates.

Example:

```text
100 transactions
+
10 new transactions
=
110 transactions
```

Gold should update the existing aggregate rather than append a second,
independent aggregate row.

Gold currently exposes:

```text
daily_payment_metrics
merchant_payment_metrics
channel_payment_metrics
fraud_operations_metrics
```

---

## Why CDF Is Not Enabled Everywhere

CDF is enabled where a table participates in change-sensitive downstream
processing.

It is not enabled on every dataset because doing so does not automatically
make a pipeline incremental.

For append-only streams:

```text
readStream + checkpoint
```

already provides incremental processing.

CDF is most valuable when consumers need to understand exactly which rows were
inserted, updated or deleted.

---

## Future Milestone 6

Milestone 6 adds:

- Lakeflow expectations
- invalid-record handling
- event deduplication
- late-event handling
- out-of-order event handling
- AUTO CDC
- SCD Type 1
- SCD Type 2
- delete handling
- CDC sequencing

The synthetic CDC and streaming scenarios generated in Milestone 2 are reused
for these tests.