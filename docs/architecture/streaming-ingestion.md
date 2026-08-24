# Streaming Ingestion Architecture

## Purpose

The streaming ingestion layer demonstrates secure, governed, real-time payment
event ingestion from Amazon MSK into Databricks Lakeflow Declarative Pipelines.

## Architecture

```text
Synthetic Payment Generator
        |
        v
Python Kafka Replay Producer
        |
        | SASL/OAUTHBEARER + AWS IAM
        v
Amazon MSK
payments.events.v1
        |
        | TLS + IAM
        v
Unity Catalog Service Credential
payments_msk_dev
        |
        v
Databricks Serverless
Lakeflow Declarative Pipeline
        |
        v
payments_dev.bronze.payment_events