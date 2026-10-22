# EPIP financial assurance — no-Databricks execution plan

**Constraint:** No active Databricks workspace. Do not require Databricks access, paid infrastructure, credentials or a deployed Kafka cluster to execute the benchmark.

## Two distinct tracks

1. **Local benchmark (now):** Standard-library Python reconciliation and an independent expected-results manifest; extend with deterministic fixtures, multiple seeds, failure injection, history reconstruction and measured costs/latency. A future optional local PySpark integration can test Spark transformations, but must never be represented as a Lakeflow execution.
2. **Lakeflow integration (deferred):** The existing Databricks code remains unchanged. No claims about actual Lakeflow correctness, recovery or performance until a workspace is available and tests are executed there.

## Run the committed v0.1 slice

From the repository root with Python 3.11+:

```bash
python -m benchmarks.financial_assurance.runner --output artifacts/benchmark-results/financial-assurance-v0.1.json
python -m pytest tests/benchmark/test_financial_assurance.py -q
```

The runner uses only the standard library. pytest is required only for the test command. This document does not assert these commands have been executed.

## Acceptance requirements for the expanded benchmark

- Generate reproducible fixtures and record seed, input checksum, benchmark version, Python version, host/platform and run timestamp.
- Keep the expected-results oracle independent of the tested processing implementation.
- Test at least one clean-data negative control and one legitimately late event that must be preserved.
- Measure recall, precision, false positives, false negatives, valid retention, duplicate leakage, output equivalence, throughput and resource costs.
- Compare to a **reasonable** baseline with documented controls, not solely to the intentionally minimal v0.1 baseline.
- Retain failed test runs and limitations alongside successful measurements.
- Begin with bank-style payment events; add processor and network scenarios only once their schemas and business rules differ meaningfully.
- Publish artifacts from real executions; never copy illustrative targets into a results table.

## Evidence boundaries

Passing local simulations supports reproducibility of the **local integrity method** under the tested synthetic cases. It does not independently verify the original Lakeflow data path, prove real-world fraud reduction, establish external adoption, or establish effectiveness beyond the tested synthetic scenarios.

## Next engineering sequence

1. Seeded synthetic event generator and frozen oracle manifests.
2. Event-id duplicate and conflicting-payload experiment.
3. Late/out-of-order event and CDC/SCD history experiment.
4. Transaction-level reconciliation and quarantine.
5. Restart/replay from persisted local checkpoint state.
6. Multi-seed scaling, fair baseline comparison, machine-readable result bundle and technical paper.
