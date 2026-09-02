# Milestone 13 Demo Runbook — Agent Evaluation and Regression Gates

## 1. Create the branch

```powershell
git checkout main
git pull origin main
git checkout -b feature/m13-agent-evaluation
```

## 2. Copy the M13 files

Copy the supplied files into the same relative paths in the EPIP repository.

No `databricks.yml` change is required because the repository already includes:

```yaml
include:
  - bundle.targets.yml
  - bundle/resources/*.yml
```

## 3. Validate local code

```powershell
uv sync
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -v
```

Fix only actual validation errors before deploying.

## 4. Validate and deploy the bundle

```powershell
databricks bundle validate -t dev -p PAYMENTS_DEV
databricks bundle deploy -t dev -p PAYMENTS_DEV
```

## 5. Create M13 governed assets

```powershell
databricks bundle run -t dev -p PAYMENTS_DEV fraud_agent_evaluation_setup
```

Expected marker:

```text
EPIP_M13_EVALUATION_ASSETS_READY
```

## 6. Verify the golden dataset

```sql
SELECT
    case_id,
    scenario_type,
    transaction_id,
    required_tools,
    citations_required,
    active
FROM payments_dev.ai.agent_evaluation_dataset
ORDER BY case_id;
```

Expected:

```text
8 active cases
```

## 7. Verify the three M13 tables

```sql
SHOW TABLES IN payments_dev.ai;
```

Confirm:

```text
agent_evaluation_dataset
agent_evaluation_results
agent_evaluation_summary
```

## 8. Configure local model credentials

```powershell
$env:ANTHROPIC_API_KEY="..."
$env:OPENAI_API_KEY="..."
```

Never commit these secrets.

## 9. Run a fast smoke test

Run two cases first:

```powershell
uv run python scripts/agents/13_evaluate_fraud_investigation_agent.py `
  --profile PAYMENTS_DEV `
  --catalog payments_dev `
  --max-cases 2
```

The smoke test verifies runtime connectivity and persistence.

Because it is a partial suite, do not treat its aggregate result as the
formal M13 regression decision.

## 10. Run the formal M13 evaluation

```powershell
uv run python scripts/agents/13_evaluate_fraud_investigation_agent.py `
  --profile PAYMENTS_DEV `
  --catalog payments_dev
```

Expected completion marker:

```text
EPIP_M13_AGENT_EVALUATION_COMPLETE
```

Desired final gate:

```text
REGRESSION_GATE=PASS
```

If the gate fails, inspect the persisted failures rather than immediately
lowering thresholds.

## 11. Inspect per-case results

```sql
SELECT
    evaluation_run_id,
    case_id,
    scenario_type,
    tools_used,
    tool_call_count,
    tool_selection_score,
    tool_argument_score,
    tool_efficiency_score,
    groundedness_score,
    evidence_completeness_score,
    citation_score,
    overall_score,
    case_pass,
    failure_reasons,
    trace_id,
    created_at
FROM payments_dev.ai.agent_evaluation_results
ORDER BY created_at DESC;
```

## 12. Inspect the latest summary

```sql
SELECT *
FROM payments_dev.ai.agent_evaluation_summary
ORDER BY created_at DESC
LIMIT 1;
```

## 13. Inspect judge rationale for failures

```sql
SELECT
    case_id,
    scenario_type,
    overall_score,
    case_pass,
    failure_reasons,
    judge_rationale,
    trace_id
FROM payments_dev.ai.agent_evaluation_results
WHERE case_pass = false
ORDER BY created_at DESC;
```

## 14. Root-cause with MLflow

Open:

```text
/Shared/epip-dev-fraud-agent-evaluation
```

Use the persisted `trace_id` to inspect the corresponding M12 agent trace.

Review:

- Claude tool selection;
- tool arguments;
- transaction scope;
- AI Search retrieval;
- final response;
- deterministic scores;
- judge rationale.

## 15. Regression-gate interpretation

Hard failures:

```text
transaction_scope
safety
human_review
response_structure
required_tools
```

Quality failures can include:

```text
overall_case_score
citation_correctness
tool_selection
tool_arguments
tool_efficiency
groundedness
evidence_completeness
```

Do not reduce a gate only to make the benchmark green. First determine
whether the problem is the prompt, tool behavior, retrieval, test-case
expectation, or judge.

## 16. Final validation

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -v

databricks bundle validate -t dev -p PAYMENTS_DEV

git status
git diff --stat
git diff
```

## 17. Commit and PR

```powershell
git add .
git commit -m "feat(agent): add evaluation and regression gates"
git push -u origin feature/m13-agent-evaluation
```

Create one PR for the complete milestone.

Update `README.md` and `docs/PROJECT_STATUS.md` only after the formal
evaluation has passed.
