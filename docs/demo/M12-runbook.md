# Milestone 12 Demo Runbook — Governed Fraud Investigation Agent

## 1. Purpose

This runbook demonstrates the EPIP Milestone 12 governed Fraud Investigation Agent.

The demo proves that the platform can combine governed Databricks evidence, point-in-time fraud features, Champion ML predictions, Databricks AI Search, Claude tool calling, MLflow tracing, durable investigation history, and human-in-the-loop controls.

---

## 2. Prerequisites

Required Databricks profile:

```text
PAYMENTS_DEV
```

Required environment variable:

```powershell
$env:ANTHROPIC_API_KEY="..."
```

Do not commit API keys into Git.

---

## 3. Required Databricks Assets

```text
payments_dev.ai.agent_transaction_context
payments_dev.ai.agent_fraud_evidence
payments_dev.ai.get_transaction_context
payments_dev.ai.get_fraud_evidence
payments_dev.ai.fraud_investigation_knowledge_index
payments_dev.ai.fraud_agent_investigations
```

AI Search endpoint:

```text
epip-dev-fraud-knowledge-search
```

MLflow experiment:

```text
/Shared/epip-dev-fraud-agent
```

---

## 4. Validate the Repository

```powershell
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest -v
```

---

## 5. Validate and Deploy the Bundle

```powershell
databricks bundle validate -t dev -p PAYMENTS_DEV
databricks bundle deploy -t dev -p PAYMENTS_DEV
```

---

## 6. Run M12 Setup

```powershell
databricks bundle run -t dev -p PAYMENTS_DEV fraud_investigation_agent_setup
```

The setup contains two serverless tasks:

```text
build_agent_evidence
        |
        v
create_agent_investigation_store
```

Both should succeed.

---

## 7. Verify Investigation History

```sql
SELECT COUNT(*)
FROM payments_dev.ai.fraud_agent_investigations;
```

```sql
SELECT
    investigation_id,
    transaction_id,
    generation_model,
    tools_used,
    tool_call_count,
    trace_id,
    duration_seconds,
    created_at
FROM payments_dev.ai.fraud_agent_investigations
ORDER BY created_at DESC;
```

---

## 8. Run a Single Investigation

```powershell
uv run python scripts/agents/12_run_fraud_investigation_agent.py `
  --profile PAYMENTS_DEV `
  --catalog payments_dev `
  --transaction-id txn-00000001
```

Expected marker:

```text
EPIP_M12C_FRAUD_AGENT_READY
```

---

## 9. Run Without Persistence

```powershell
uv run python scripts/agents/12_run_fraud_investigation_agent.py `
  --profile PAYMENTS_DEV `
  --catalog payments_dev `
  --transaction-id txn-00000001 `
  --no-persist
```

---

## 10. Run via ResponsesAgent

```powershell
uv run python scripts/agents/12_run_fraud_investigation_agent.py `
  --profile PAYMENTS_DEV `
  --catalog payments_dev `
  --transaction-id txn-00000001 `
  --interface responses
```

The ResponsesAgent exposes transaction ID, generation model, trace ID, tool-call count, tools used, and tool execution records.

---

## 11. Run the Four Portfolio Scenarios

```powershell
uv run python scripts/agents/12_run_agent_demo_scenarios.py `
  --profile PAYMENTS_DEV `
  --catalog payments_dev
```

Expected marker:

```text
EPIP_M12C_DEMO_SCENARIOS_COMPLETE
```

---

## 12. Scenario Validation

### Scenario 1 — Strong Risk Evidence

The agent should identify supported risk indicators and model evidence without declaring definitive fraud.

### Scenario 2 — Cross-Border Counterexample

The agent should demonstrate that cross-border activity is context, not proof of fraud, and should consider counter-indicators.

### Scenario 3 — Duplicate Kafka Delivery

The scenario uses:

```text
payments_dev.bronze.payment_events
```

with `event_id`, `transaction_id`, `delivery_scenario`, and `kafka_offset` to demonstrate that multiple physical Kafka deliveries do not automatically mean multiple financial transactions.

### Scenario 4 — Insufficient Evidence

The agent should explicitly state uncertainty, missing evidence, and appropriate next investigation steps.

---

## 13. Review Persisted Results

```sql
SELECT
    investigation_id,
    transaction_id,
    generation_model,
    tools_used,
    tool_call_count,
    risk_indicators,
    counter_indicators,
    knowledge_sources,
    trace_id,
    duration_seconds,
    created_at
FROM payments_dev.ai.fraud_agent_investigations
ORDER BY created_at DESC;
```

---

## 14. Review Investigation Content

```sql
SELECT
    transaction_id,
    assessment,
    risk_indicators,
    counter_indicators,
    model_signal,
    evidence_reviewed,
    knowledge_sources,
    limitations,
    recommended_next_steps
FROM payments_dev.ai.fraud_agent_investigations
ORDER BY created_at DESC;
```

---

## 15. Review Tool Selection

```sql
SELECT
    transaction_id,
    tools_used,
    tool_call_count
FROM payments_dev.ai.fraud_agent_investigations
ORDER BY created_at DESC;
```

Different investigations may legitimately use different subsets of the three approved tools.

---

## 16. Verify MLflow Trace IDs

```sql
SELECT
    investigation_id,
    transaction_id,
    trace_id
FROM payments_dev.ai.fraud_agent_investigations
WHERE trace_id IS NOT NULL
ORDER BY created_at DESC;
```

Open:

```text
/Shared/epip-dev-fraud-agent
```

and locate the corresponding traces.

---

## 17. Security Demonstration

The agent has only:

```text
get_transaction_context
get_fraud_evidence
search_fraud_knowledge
```

It has no arbitrary SQL tool and no state-changing payment or customer tools.

---

## 18. Interview Demo Flow

1. Explain why a fraud model score alone is insufficient.
2. Show the governed agent architecture.
3. Run one investigation.
4. Show dynamic tool selection in MLflow.
5. Show the structured investigation response.
6. Show the persisted investigation row.
7. Explain no arbitrary SQL, no action tools, no future-label leakage, point-in-time features, and mandatory human review.
8. Explain that M13 adds formal agent evaluation and regression gates.

---

## 19. Final M12 Validation

```powershell
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest -v
databricks bundle validate -t dev -p PAYMENTS_DEV
git status
git diff --stat
git diff
```

Then:

```powershell
git add .
git commit -m "feat(agent): complete governed fraud investigation agent"
git push -u origin feature/m12-fraud-investigation-agent
```
