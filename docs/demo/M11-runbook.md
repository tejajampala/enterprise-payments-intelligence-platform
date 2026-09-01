# EPIP Milestone 11 — Serverless retrieval + local LLM evaluation

## Why this split exists

The current Databricks development workspace has two proven constraints:

1. Databricks Jobs only support serverless compute in this workspace.
2. Serverless outbound access to `api.anthropic.com` is blocked by network policy.
3. Databricks-hosted premium model access has also returned a Databricks-set
   rate limit of `0`.

M11 therefore freezes retrieval inside Databricks, then evaluates that frozen
context from the local development machine.

## One-time local dependencies

From the repository root:

```powershell
uv add --group dev "mlflow[databricks]==3.15.2"
uv add --group dev "databricks-sdk==0.133.0"
uv add --group dev "databricks-sql-connector==4.4.0"
uv add --group dev "anthropic==0.121.0"
uv add --group dev "openai==3.6.0"
```

## Local quality checks

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -v
```

## Validate and deploy the Databricks part

```powershell
databricks bundle validate -t dev -p PAYMENTS_DEV
databricks bundle deploy -t dev -p PAYMENTS_DEV
databricks bundle run -t dev -p PAYMENTS_DEV rag_vector_search
```

The Databricks job ends after:

```text
build_fraud_knowledge_base
        ->
build_ai_search_index
        ->
validate_retrieval
```

The last task writes the exact top-3 formal retrieval result to:

```text
payments_dev.ai.rag_retrieval_evaluation
```

## Set external-provider keys only in the local PowerShell session

```powershell
$env:ANTHROPIC_API_KEY="<your-anthropic-key>"
$env:OPENAI_API_KEY="<your-openai-key>"
```

Do not commit these values.

## Run local RAG generation and evaluation

```powershell
uv run python scripts/rag/11_evaluate_rag_quality_local.py `
  --profile PAYMENTS_DEV `
  --catalog payments_dev `
  --generation-model claude-sonnet-4-6 `
  --judge-model gpt-4o-mini `
  --experiment-name /Shared/epip-dev-fraud-rag
```

The runner:

1. uses `PAYMENTS_DEV` unified authentication,
2. discovers the available Databricks SQL warehouse,
3. reads the frozen retrieval result,
4. replays it in an MLflow `RETRIEVER` span,
5. generates answers with Anthropic,
6. judges them with OpenAI,
7. writes MLflow traces/evaluation to Databricks,
8. appends `payments_dev.ai.rag_quality_metrics`, and
9. replaces `payments_dev.ai.rag_demo_responses`.

If you prefer a specific warehouse:

```powershell
uv run python scripts/rag/11_evaluate_rag_quality_local.py `
  --profile PAYMENTS_DEV `
  --warehouse-id <warehouse-id>
```