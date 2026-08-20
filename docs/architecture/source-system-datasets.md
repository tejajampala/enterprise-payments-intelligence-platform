# Local Source-System Datasets

## Purpose

The Enterprise Payments Intelligence Platform converts the canonical synthetic payments
domain into reproducible representations of the source systems that will later feed the
Databricks platform.

Generated source datasets are not committed to Git.

They can be recreated deterministically from the synthetic-data seed.

---

## Source Architecture

```text
Canonical Domain
        |
        v
Synthetic Generator
        |
        v
Controlled Scenario Layer
        |
        v
Source Dataset Exporter
        |
        +-----------------------------+
        |              |              |
        v              v              v
   PostgreSQL         S3            Kafka
      style          style           style
       CSV           JSONL           JSONL
```

---

## PostgreSQL Representation

PostgreSQL-style datasets contain:

```text
snapshots/
    customers.csv
    accounts.csv
    merchants.csv
    fraud_cases.csv

cdc/
    customers.csv
    accounts.csv
    merchants.csv
```

The snapshot files represent the initial operational state.

The CDC files contain controlled changes such as:

```text
Customer version 1
Customer version 3
Customer version 2
```

This deliberately simulates out-of-order CDC delivery.

Later these datasets will be used to seed and exercise a PostgreSQL-compatible source.

---

## S3 Representation

Historical payment transactions are written as JSON Lines and partitioned by event date.

Example:

```text
historical_transactions/
    clean/
        event_date=2026-07-01/
            transactions.jsonl

        event_date=2026-07-02/
            transactions.jsonl
```

Controlled scenarios are separated from the clean baseline:

```text
scenarios/
    duplicates/
        transactions.jsonl

    invalid/
        transactions.jsonl
```

This makes it possible to run clean ingestion and fault-injection demonstrations
independently.

---

## Kafka Representation

Payment events are written as replayable Kafka-style envelopes.

Each record contains:

```text
topic
message_key
simulated_arrival_at
scenario
payload
```

The business transaction ID is used as the message key.

This allows all lifecycle events for the same transaction to be routed consistently when
the records are later published to Kafka.

---

## Clean and Scenario Separation

The source layout preserves the project design principle:

```text
clean data
    |
    +-- normal processing

scenario data
    |
    +-- duplicates
    +-- invalid records
    +-- out-of-order events
    +-- late events
```

This allows deterministic demonstrations of both successful processing and failure
handling.

---

## Reproducibility

The default dataset uses:

```text
seed = 42
```

Generated records are therefore reproducible across:

```text
developer workstation
CI
Databricks development environment
future AWS integration tests
```

The generated `data/` directory is ignored by Git.

Only the generator, scenario logic, exporter, tests, and documentation are version
controlled.