# Feature Engineering Architecture

## Purpose

Milestone 7 introduces governed, reusable features for machine-learning
workloads.

The initial consumer is the Milestone 8 payment-fraud model.

## Unity Catalog Feature Store

EPIP uses Unity Catalog Delta feature tables with primary-key constraints.

Feature tables:

- `transaction_fraud_features`
- `customer_behavior_features`
- `merchant_behavior_features`

Training dataset:

- `fraud_training_dataset`

## Transaction Features

Transaction features represent immutable information available from the
payment transaction.

Examples:

- amount
- logarithmic amount
- hour of day
- weekend indicator
- cross-border indicator
- card-not-present indicator
- payment channel indicators
- payment-method indicators

Fraud investigation outcomes are deliberately excluded.

## Customer Behaviour Features

Customer behaviour is calculated from transactions that occurred strictly
before the transaction being scored.

Windows include:

- 1 day
- 7 days
- 30 days

Examples:

- prior transaction count
- prior payment amount
- average payment amount
- decline rate
- foreign payment rate
- card-not-present rate

## Merchant Behaviour Features

Equivalent historical features are calculated for merchants.

These help detect behaviour such as sudden volume or transaction-pattern
changes.

## Point-in-Time Correctness

Customer and merchant feature tables use composite keys:

```text
entity_id
feature_timestamp TIMESERIES