from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]

BUNDLE_RESOURCE = ROOT / "bundle/resources/rag_vector_search.yml"

KNOWLEDGE_NOTEBOOK = "notebooks/rag/11_build_fraud_knowledge_base.py"
INDEX_NOTEBOOK = "notebooks/rag/11_build_ai_search_index.py"
RETRIEVAL_NOTEBOOK = "notebooks/rag/11_validate_retrieval.py"
LOCAL_EVALUATION_RUNNER = "scripts/rag/11_evaluate_rag_quality_local.py"


def _read(relative_path: str) -> str:
    """Read one UTF-8 repository file."""

    return (ROOT / relative_path).read_text(encoding="utf-8")


def _load_yaml(
    path: Path,
) -> dict[str, Any]:
    """Load one YAML file."""

    with path.open(encoding="utf-8") as file:
        content = yaml.safe_load(file)

    assert isinstance(
        content,
        dict,
    )

    return content


def _bundle_config() -> dict[str, Any]:
    """Load the M11 bundle resource."""

    return _load_yaml(BUNDLE_RESOURCE)


def _rag_job() -> dict[str, Any]:
    """Return the M11 RAG job."""

    return _bundle_config()["resources"]["jobs"]["rag_vector_search"]


def _rag_tasks() -> dict[str, dict[str, Any]]:
    """Return M11 tasks by task key."""

    return {task["task_key"]: task for task in _rag_job()["tasks"]}


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


def test_rag_bundle_resource_exists() -> None:
    assert BUNDLE_RESOURCE.exists()


def test_knowledge_notebook_exists() -> None:
    assert (ROOT / KNOWLEDGE_NOTEBOOK).exists()


def test_ai_search_index_notebook_exists() -> None:
    assert (ROOT / INDEX_NOTEBOOK).exists()


def test_retrieval_notebook_exists() -> None:
    assert (ROOT / RETRIEVAL_NOTEBOOK).exists()


def test_local_rag_evaluation_runner_exists() -> None:
    assert (ROOT / LOCAL_EVALUATION_RUNNER).exists()


# ---------------------------------------------------------------------------
# Bundle resources
# ---------------------------------------------------------------------------


def test_ai_schema_exists() -> None:
    schemas = _bundle_config()["resources"]["schemas"]

    assert "ai_schema" in schemas


def test_ai_schema_uses_bundle_catalog() -> None:
    schema = _bundle_config()["resources"]["schemas"]["ai_schema"]

    assert schema["name"] == "ai"
    assert schema["catalog_name"] == "${var.catalog_name}"


def test_ai_search_endpoint_exists() -> None:
    endpoints = _bundle_config()["resources"]["vector_search_endpoints"]

    assert "fraud_knowledge_search_endpoint" in endpoints


def test_ai_search_endpoint_is_standard() -> None:
    endpoint = _bundle_config()["resources"]["vector_search_endpoints"]["fraud_knowledge_search_endpoint"]

    assert endpoint["endpoint_type"] == "STANDARD"


# ---------------------------------------------------------------------------
# Serverless-only workspace architecture
# ---------------------------------------------------------------------------


def test_rag_job_has_three_databricks_tasks() -> None:
    assert set(_rag_tasks()) == {
        "build_fraud_knowledge_base",
        "build_ai_search_index",
        "validate_retrieval",
    }


def test_rag_job_has_no_classic_job_clusters() -> None:
    assert "job_clusters" not in _rag_job()


def test_rag_job_has_serverless_environment() -> None:
    environment_keys = {environment["environment_key"] for environment in _rag_job()["environments"]}

    assert "rag_env" in environment_keys


def test_all_databricks_tasks_use_serverless_environment() -> None:
    for task in _rag_tasks().values():
        assert task["environment_key"] == "rag_env"
        assert "job_cluster_key" not in task
        assert "existing_cluster_id" not in task


def test_bundle_does_not_run_external_llm_evaluation() -> None:
    source = _read("bundle/resources/rag_vector_search.yml")

    assert "evaluate_rag_quality" not in {task["task_key"] for task in _rag_job()["tasks"]}

    assert "anthropic==" not in source
    assert "openai==" not in source


def test_serverless_environment_pins_ai_search_sdk() -> None:
    environment = next(
        environment for environment in _rag_job()["environments"] if environment["environment_key"] == "rag_env"
    )

    dependencies = environment["spec"]["dependencies"]

    assert "databricks-ai-search==0.78" in dependencies


# ---------------------------------------------------------------------------
# Task graph
# ---------------------------------------------------------------------------


def test_build_knowledge_has_no_dependency() -> None:
    task = _rag_tasks()["build_fraud_knowledge_base"]

    assert task.get("depends_on") is None


def test_ai_search_depends_on_knowledge() -> None:
    task = _rag_tasks()["build_ai_search_index"]

    assert task["depends_on"] == [{"task_key": "build_fraud_knowledge_base"}]


def test_retrieval_depends_on_ai_search() -> None:
    task = _rag_tasks()["validate_retrieval"]

    assert task["depends_on"] == [{"task_key": "build_ai_search_index"}]


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------


def test_knowledge_source_has_change_data_feed() -> None:
    source = _read(KNOWLEDGE_NOTEBOOK)

    assert "delta.enableChangeDataFeed" in source


def test_knowledge_source_has_row_tracking() -> None:
    source = _read(KNOWLEDGE_NOTEBOOK)

    assert "delta.enableRowTracking" in source


def test_knowledge_source_has_chunk_primary_key() -> None:
    source = _read(KNOWLEDGE_NOTEBOOK)

    assert "PRIMARY KEY (chunk_id)" in source


def test_knowledge_uses_idempotent_merge() -> None:
    source = _read(KNOWLEDGE_NOTEBOOK)

    assert "MERGE INTO" in source
    assert "WHEN MATCHED" in source
    assert "WHEN NOT MATCHED" in source


def test_knowledge_does_not_full_delete_before_insert() -> None:
    source = _read(KNOWLEDGE_NOTEBOOK)

    assert "DELETE FROM " not in source or "MERGE INTO" in source


def test_evaluation_dataset_has_expected_document() -> None:
    source = _read(KNOWLEDGE_NOTEBOOK)

    assert "expected_doc_id" in source


def test_evaluation_dataset_has_expected_facts() -> None:
    source = _read(KNOWLEDGE_NOTEBOOK)

    assert "expected_facts" in source


def test_evaluation_dataset_has_twelve_queries() -> None:
    source = _read(KNOWLEDGE_NOTEBOOK)

    assert '"q001"' in source
    assert '"q012"' in source


# ---------------------------------------------------------------------------
# AI Search
# ---------------------------------------------------------------------------


def test_current_ai_search_client_is_used() -> None:
    source = _read(INDEX_NOTEBOOK)

    assert "AISearchClient" in source
    assert "VectorSearchClient" not in source


def test_triggered_delta_sync_is_used() -> None:
    source = _read(INDEX_NOTEBOOK)

    assert "create_delta_sync_index" in source
    assert 'pipeline_type="TRIGGERED"' in source


def test_chunk_text_is_embedding_source() -> None:
    source = _read(INDEX_NOTEBOOK)

    assert 'embedding_source_column="chunk_text"' in source


def test_qwen_embedding_model_is_configured() -> None:
    source = _read("bundle/resources/rag_vector_search.yml")

    assert "databricks-qwen3-embedding-0-6b" in source


def test_index_validates_cdf() -> None:
    source = _read(INDEX_NOTEBOOK)

    assert "delta.enableChangeDataFeed" in source


def test_index_has_hybrid_smoke_test() -> None:
    source = _read(INDEX_NOTEBOOK)

    assert 'query_type="HYBRID"' in source
    assert "smoke" in source.lower()


# ---------------------------------------------------------------------------
# Frozen retrieval
# ---------------------------------------------------------------------------


def test_retrieval_uses_hybrid_search() -> None:
    source = _read(RETRIEVAL_NOTEBOOK)

    assert 'RETRIEVAL_METHOD = "HYBRID"' in source


def test_retrieval_results_table_is_created() -> None:
    source = _read(RETRIEVAL_NOTEBOOK)

    assert "rag_retrieval_evaluation" in source


def test_retrieval_generates_run_id() -> None:
    source = _read(RETRIEVAL_NOTEBOOK)

    assert "uuid4" in source
    assert "retrieval_run_id" in source


def test_retrieval_persists_exact_documents() -> None:
    source = _read(RETRIEVAL_NOTEBOOK)

    assert '"retrieved_documents"' in source
    assert '"rank"' in source
    assert '"chunk_text"' in source


def test_retrieval_uses_explicit_nested_schema() -> None:
    source = _read(RETRIEVAL_NOTEBOOK)

    assert "retrieved_document_schema" in source
    assert "retrieval_results_schema" in source
    assert "ArrayType" in source
    assert "StructType" in source


def test_retrieval_records_hit_at_one() -> None:
    assert "hit_at_1" in _read(RETRIEVAL_NOTEBOOK)


def test_retrieval_records_hit_at_three() -> None:
    assert "hit_at_3" in _read(RETRIEVAL_NOTEBOOK)


def test_retrieval_records_mrr() -> None:
    assert "reciprocal_rank" in _read(RETRIEVAL_NOTEBOOK)


def test_retrieval_records_empty_rate() -> None:
    assert "empty_retrieval" in _read(RETRIEVAL_NOTEBOOK)


def test_retrieval_has_pre_llm_quality_gates() -> None:
    source = _read(RETRIEVAL_NOTEBOOK)

    assert "MIN_HIT_AT_1" in source
    assert "MIN_RECALL_AT_3" in source
    assert "MIN_MRR" in source
    assert "MAX_EMPTY_RETRIEVAL_RATE" in source


# ---------------------------------------------------------------------------
# Local provider evaluation architecture
# ---------------------------------------------------------------------------


def test_local_runner_defaults_to_payments_profile() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert 'default="PAYMENTS_DEV"' in source


def test_local_runner_uses_cli_profile_auth() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "WorkspaceClient(" in source
    assert "Config(" in source
    assert "profile=profile" in source


def test_local_runner_uses_sql_warehouse() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "workspace.warehouses.list" in source
    assert "sql.connect(" in source
    assert "warehouse_id" in source


def test_local_runner_reuses_unified_auth_token() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "config.authenticate()" in source
    assert 'headers.get("Authorization"' in source


def test_local_runner_reads_frozen_retrieval_table() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "rag_retrieval_evaluation" in source
    assert "retrieval_run_id" in source
    assert "retrieved_documents_json" in source


def test_formal_local_evaluation_does_not_query_ai_search() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "AISearchClient" not in source
    assert "similarity_search" not in source


def test_local_runner_uses_direct_anthropic() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "from anthropic import Anthropic" in source
    assert "anthropic_client.messages.create" in source


def test_local_runner_uses_direct_openai() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "from openai import OpenAI" in source
    assert "openai_client.chat.completions.create" in source


def test_local_runner_reads_keys_from_environment() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "require_environment_variable" in source
    assert '"ANTHROPIC_API_KEY"' in source
    assert '"OPENAI_API_KEY"' in source
    assert "dbutils.secrets" not in source


def test_local_runner_has_connectivity_smoke_tests() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "EPIP_ANTHROPIC_READY" in source
    assert "EPIP_OPENAI_READY" in source


# ---------------------------------------------------------------------------
# MLflow tracing and evaluation
# ---------------------------------------------------------------------------


def test_mlflow_tracks_to_databricks_profile() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert 'f"databricks://{args.profile}"' in source


def test_retriever_span_replays_frozen_documents() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert '@mlflow.trace(span_type="RETRIEVER")' in source
    assert "def replay_validated_retrieval" in source


def test_parser_span_is_traced() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert '@mlflow.trace(span_type="PARSER")' in source


def test_chat_model_span_is_traced() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert '@mlflow.trace(span_type="CHAT_MODEL")' in source


def test_chain_span_is_traced() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert '@mlflow.trace(span_type="CHAIN")' in source


def test_retriever_returns_mlflow_documents() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "from mlflow.entities import Document" in source
    assert "Document(" in source
    assert '"doc_uri"' in source


def test_mlflow_genai_evaluate_is_used() -> None:
    assert "mlflow.genai.evaluate" in _read(LOCAL_EVALUATION_RUNNER)


def test_rag_scorers_are_configured() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    for scorer_name in (
        "RetrievalRelevance",
        "RetrievalSufficiency",
        "RetrievalGroundedness",
        "RelevanceToQuery",
        "Safety",
    ):
        assert scorer_name in source


def test_valid_citation_scorer_rejects_invented_sources() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "def valid_source_citations" in source
    assert "cited_chunk_ids.issubset" in source


def test_both_mlflow_concurrency_limits_exist() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "MLFLOW_GENAI_EVAL_MAX_WORKERS" in source
    assert "MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS" in source


# ---------------------------------------------------------------------------
# Quality persistence
# ---------------------------------------------------------------------------


def test_quality_history_table_is_written() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "rag_quality_metrics" in source
    assert "INSERT INTO" in source


def test_quality_history_records_retrieval_run_id() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert '"retrieval_run_id"' in source


def test_quality_history_records_execution_mode() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert '"execution_mode": "local_external_provider"' in source


def test_quality_history_records_valid_citation_rate() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "valid_citation_rate" in source
    assert "MIN_VALID_CITATION_RATE" in source


def test_quality_history_is_persisted_before_failure() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    insert_position = source.find("insert_quality_history(")
    failure_position = source.rfind("Milestone 11 RAG quality gates failed")

    assert insert_position >= 0
    assert failure_position >= 0
    assert insert_position < failure_position


def test_governed_demo_table_is_written() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "rag_demo_responses" in source
    assert "contains_only_valid_source_citations" in source


def test_local_runner_can_fail_quality_gate() -> None:
    source = _read(LOCAL_EVALUATION_RUNNER)

    assert "Milestone 11 RAG quality gates failed" in source
