# Enterprise MLOps Model Lifecycle

## Purpose

Milestone 10 introduces a governed production lifecycle for machine-learning
models created by the Enterprise Payments Intelligence Platform.

## Model Development vs MLOps

Milestones 8 and 9 answer:

- which model performs best?
- what threshold should fraud detection use?
- which forecasting method outperforms the baseline?

Milestone 10 answers:

- which artifact is allowed into the registry?
- which version is the current production model?
- how is a previous model retained for rollback?
- how is the model served?
- how does batch inference find the approved version?
- how is promotion audited?

## Unity Catalog Model Registry

Registered model:

`payments_dev.models.fraud_detection_model`

Forecast model, when the selected forecasting method is a learned model:

`payments_dev.models.payment_volume_forecaster`

Unity Catalog provides governance, lineage, access control and model lifecycle
management.

## Model Aliases

EPIP uses:

- `Candidate`
- `Champion`
- `PreviousChampion`

Aliases replace hard-coded model versions in consumers.

For example:

`models:/payments_dev.models.fraud_detection_model@Champion`

allows batch inference to automatically consume the currently approved model.

## Fraud Quality Gate

A fraud model must:

- have a valid MLflow model artifact
- have finite evaluation metrics
- outperform the fraud prevalence baseline using Average Precision
- meet the configured minimum recall
- have positive F2 performance

Only models passing these gates are promoted.

## Forecast Quality Gate

Forecasting must have finite WAPE and remain below the configured maximum.

If the selected method is a learned model, it is registered and promoted.

If the seasonal-naive baseline wins, it remains a governed operational
forecasting policy instead of being artificially represented as a learned
model.

## Serving Package

The training classifier is wrapped in a production MLflow PythonModel.

The serving contract returns:

- `fraud_probability`
- `predicted_fraud`

The decision threshold selected during model validation is packaged with the
production model.

## Real-Time Serving

The Champion fraud model is deployed to:

`epip-dev-fraud-serving`

The endpoint uses:

- CPU serving
- Small workload size
- scale to zero

The deployment process resolves the Champion alias to the concrete registered
model version and updates the endpoint.

## Batch Inference

Batch scoring loads:

`models:/payments_dev.models.fraud_detection_model@Champion`

The scoring pipeline therefore contains no hard-coded version number.

Output:

`payments_dev.ml.fraud_batch_predictions`

## Rollback

Before a new Champion is assigned, the current Champion becomes:

`PreviousChampion`

Rollback can therefore be performed by reassigning the Champion alias to the
previous approved version and updating the serving endpoint.

## Auditability

Lifecycle actions are written to:

`payments_dev.ml.model_lifecycle_audit`

The audit contains:

- source model artifact
- registered model
- model version
- evaluation metrics
- quality-gate outcome
- selected method
- lifecycle status
- promotion timestamp

## Future Extensions

Milestone 15 adds full GitHub-driven enterprise CI/CD.

Milestone 17 adds production model and platform monitoring.