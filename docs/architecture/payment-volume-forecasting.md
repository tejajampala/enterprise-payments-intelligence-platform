# Payment Volume Forecasting Architecture

## Purpose

Milestone 9 introduces time-series forecasting for daily enterprise payment
transaction volume.

The business use case is operational capacity and payment-volume planning.

## Source

Forecasting consumes:

`payments_dev.gold.daily_payment_metrics`

Currency-level metrics are aggregated into one enterprise-wide daily
transaction-volume series.

## Continuous Calendar

The time series is reindexed to a continuous daily calendar.

Days without Gold records are represented as zero transaction-volume days.

## Leakage-Safe Features

Forecast features use only information available before the forecast date.

Features include:

- day of week
- day of month
- month
- weekend indicator
- cyclical weekday encoding
- 1-day lag
- 2-day lag
- 3-day lag
- 7-day lag
- optional 14-day lag
- 3-day rolling statistics
- 7-day rolling statistics
- optional 14-day rolling statistics

Rolling features are shifted by one day before calculation so the current
target value cannot leak into its own features.

## Candidate Forecasting Approaches

Three approaches are compared:

1. seven-day seasonal-naive baseline
2. Ridge regression
3. histogram gradient boosting

A complex model must outperform the simple baseline to be selected.

## Temporal Evaluation

Random splitting is not used.

Data is ordered chronologically:

```text
Oldest data
    ↓
Training
    ↓
Validation
    ↓
Untouched test period
    ↓
Newest data