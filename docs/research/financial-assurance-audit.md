# EPIP Financial Assurance: Initial Capability Audit and Benchmark v0.1

## Evidence scope

Audited against the repository source on 2026-10-20. This is a *source inspection*, not
a completed live Databricks/Lakeflow validation. The benchmark added in this branch is a
local Python simulation, not a claim of measured production-pipeline effectiveness.

| Capability | Existing EPIP evidence | Verification gap |
| --- | --- | --- |
| Duplicate streaming delivery | `pipelines/silver/payment_event_trust.py`, `tests/unit/test_streaming_event_trust.py` | Existing test asserts source patterns; compare actual outputs to oracle across replay and restart |
| Late and out-of-order events | `src/payments_intelligence/synthetic/scenarios.py`, streaming trust tests | Validate outcomes, boundary times, retention and false positives using measured runs |
| CDC/SCD and delete | `pipelines/silver/master_data_cdc.py`, `sql/reconciliation/06f_milestone6_reconciliation.sql` | Independent time-indexed expected history, not just SQL assertions |
| DQ and quarantine | `pipelines/silver/payment_quality.py`, `tests/unit/test_data_quality_foundation.py` | Measure invalid leakage, valid retention and evidence completeness |
| Reconciliation | `sql/reconciliation/06f_milestone6_reconciliation.sql` | Extend count comparisons with transaction-level settlement exceptions and external oracle |
| Failure recovery | Streaming checkpoints and documented restart handling | Compare before/after output, evidence lineage, restart time and replay outcomes |

## First implementation: synthetic reconciliation oracle

Run from repository root:

```bash
python -m benchmarks.financial_assurance.runner --output artifacts/benchmark-results/financial-assurance-v0.1.json
python -m pytest tests/benchmark/test_financial_assurance.py -q
```

Expected fixture: T002 amount mismatch, T003 missing settlement, T004 duplicate delivery,
and T999 unexpected settlement. The expected exception manifest is explicit and separate
from the reconciliation logic. The test also verifies a clean-data negative control.

**Important limitations:** Four synthetic source transactions and five delivery rows.
The comparison baseline is intentionally minimal and is **not** representative of a
production-grade alternative. This initial test establishes a reusable reproducibility
harness; it cannot justify claims of performance advantage, scalability, effectiveness
in real banking environments, real-world fraud reduction, institutional adoption, or
U.S. national impact. No measured results are claimed until execution outputs are
preserved and independently reproduced.

## Next steps

1. Cross-check the current README milestone status with older scenario docs that still say
   processing is future work; correct dated documentation only after verifying behavior.
2. Add configurable event-generation seeds, anomaly manifests, and dataset sizes.
3. Implement fair baseline controls and report baseline-versus-EPIP correctness and overhead.
4. Compare actual Lakeflow outputs to the independently prepared manifest.
5. Implement bank, processor and network adapters with meaningfully different rules.
6. Publish a versioned methodology, raw results, negative cases, execution metadata,
   limitations and third-party reproduction instructions.
