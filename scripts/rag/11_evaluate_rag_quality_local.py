"""Milestone 11 — Local fraud RAG quality evaluation.

Why this runner exists
----------------------
The EPIP development workspace supports serverless Databricks compute only.
The workspace serverless network policy blocks direct access to Anthropic, and
Databricks-hosted premium model access has also been unavailable in this
development account.

Therefore M11 is intentionally split into two execution zones:

Databricks serverless:
    build knowledge -> build/sync AI Search -> validate/freeze retrieval

Local development machine:
    replay frozen retrieval -> Anthropic generation -> OpenAI judges
    -> MLflow tracing/evaluation in Databricks -> governed Delta metrics

The local runner does NOT query AI Search again for the formal benchmark.
It consumes the exact top-K documents persisted by 11_validate_retrieval.py.

Required local environment variables:
    ANTHROPIC_API_KEY
    OPENAI_API_KEY

Databricks authentication uses an existing Databricks CLI configuration profile,
for example PAYMENTS_DEV.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import time
from dataclasses import dataclass
from typing import Any

import mlflow
from anthropic import Anthropic
from databricks import sql
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from mlflow.entities import Document, SpanType, Trace
from mlflow.genai import scorer
from mlflow.genai.scorers import (
    RelevanceToQuery,
    RetrievalGroundedness,
    RetrievalRelevance,
    RetrievalSufficiency,
    Safety,
)
from openai import OpenAI

# ---------------------------------------------------------------------------
# Quality gates
# ---------------------------------------------------------------------------

MIN_HIT_AT_1 = 0.60
MIN_RECALL_AT_3 = 0.80
MIN_MRR = 0.65
MAX_EMPTY_RETRIEVAL_RATE = 0.0

MIN_RETRIEVAL_RELEVANCE = 0.80
MIN_RETRIEVAL_SUFFICIENCY = 0.80
MIN_GROUNDEDNESS = 0.90
MIN_ANSWER_RELEVANCE = 0.90
MIN_VALID_CITATION_RATE = 1.00
MIN_SAFETY = 1.00

# Keep local external-provider evaluation deliberately conservative.
os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_WORKERS", "1")
os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS", "1")
os.environ.setdefault(
    "MLFLOW_GENAI_EVAL_ENABLE_SCORER_TRACING",
    "true",
)


@dataclass(frozen=True)
class EvaluationCase:
    """One frozen formal RAG-evaluation case."""

    retrieval_run_id: str
    query_id: str
    question: str
    expected_doc_id: str
    expected_facts: list[str]
    retrieved_documents: list[dict[str, Any]]
    hit_at_1: float
    hit_at_3: float
    reciprocal_rank: float
    empty_retrieval: bool


def parse_args() -> argparse.Namespace:
    """Parse local M11 runner arguments."""

    parser = argparse.ArgumentParser(
        description="Run EPIP M11 RAG generation/evaluation locally.",
    )

    parser.add_argument(
        "--profile",
        default="PAYMENTS_DEV",
        help="Databricks CLI configuration profile.",
    )

    parser.add_argument(
        "--catalog",
        default="payments_dev",
        help="Unity Catalog catalog containing the M11 ai schema.",
    )

    parser.add_argument(
        "--warehouse-id",
        default=None,
        help=("Optional Databricks SQL warehouse ID. When omitted, the runner discovers an available warehouse."),
    )

    parser.add_argument(
        "--generation-model",
        default="claude-sonnet-4-6",
        help="Anthropic model used to generate the RAG answer.",
    )

    parser.add_argument(
        "--judge-model",
        default="gpt-4o-mini",
        help="OpenAI model used by MLflow LLM judges.",
    )

    parser.add_argument(
        "--experiment-name",
        default="/Shared/epip-dev-fraud-rag",
        help="Databricks MLflow experiment path.",
    )

    return parser.parse_args()


def validate_identifier(value: str, label: str) -> str:
    """Validate a simple Unity Catalog identifier before using it in SQL."""

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Invalid {label}: {value!r}")

    return value


def require_environment_variable(name: str) -> str:
    """Return one required local secret without logging its value."""

    value = os.environ.get(name)

    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set.")

    return value


def choose_sql_warehouse(
    workspace: WorkspaceClient,
    explicit_warehouse_id: str | None,
) -> str:
    """Return a SQL warehouse ID for governed Delta reads/writes."""

    if explicit_warehouse_id:
        return explicit_warehouse_id

    warehouses = list(workspace.warehouses.list())

    if not warehouses:
        raise RuntimeError("No Databricks SQL warehouse is available to the current user.")

    running = [warehouse for warehouse in warehouses if "RUNNING" in str(getattr(warehouse, "state", "")).upper()]

    selected = running[0] if running else warehouses[0]

    warehouse_id = getattr(selected, "id", None)

    if not warehouse_id:
        raise RuntimeError("Unable to determine Databricks SQL warehouse ID.")

    warehouse_name = getattr(selected, "name", None) or warehouse_id

    print("Databricks SQL warehouse:", warehouse_name)
    print("Databricks SQL warehouse ID:", warehouse_id)

    return str(warehouse_id)


def databricks_sql_connection(
    profile: str,
    warehouse_id: str,
):
    """Open SQL connector session using the existing Databricks profile."""

    config = Config(
        profile=profile,
        warehouse_id=warehouse_id,
    )

    headers = config.authenticate()
    authorization = headers.get("Authorization", "")

    if not authorization.startswith("Bearer "):
        raise RuntimeError("Databricks profile did not provide a Bearer authentication token.")

    access_token = authorization.removeprefix("Bearer ").strip()

    http_path = config.sql_http_path

    if not http_path:
        raise RuntimeError("Unable to determine SQL warehouse HTTP path from Databricks profile.")

    return sql.connect(
        server_hostname=config.hostname,
        http_path=http_path,
        access_token=access_token,
        use_cloud_fetch=False,
        user_agent_entry="epip-m11-local-rag-evaluation",
    )


def rows_as_dicts(cursor) -> list[dict[str, Any]]:
    """Convert SQL connector result rows to ordinary dictionaries."""

    column_names = [description[0] for description in cursor.description]

    return [
        dict(
            zip(
                column_names,
                row,
                strict=False,
            )
        )
        for row in cursor.fetchall()
    ]


def load_frozen_evaluation_cases(
    connection,
    catalog: str,
) -> list[EvaluationCase]:
    """Load the exact retrieval run written by validate_retrieval."""

    retrieval_table = f"{catalog}.ai.rag_retrieval_evaluation"
    evaluation_table = f"{catalog}.ai.rag_evaluation_dataset"

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT DISTINCT retrieval_run_id
            FROM {retrieval_table}
            """
        )

        run_rows = rows_as_dicts(cursor)

    retrieval_run_ids = {str(row["retrieval_run_id"]) for row in run_rows if row.get("retrieval_run_id")}

    if len(retrieval_run_ids) != 1:
        raise RuntimeError(
            f"Expected exactly one frozen retrieval_run_id in {retrieval_table}; found {sorted(retrieval_run_ids)}"
        )

    retrieval_run_id = next(iter(retrieval_run_ids))

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                r.retrieval_run_id,
                r.query_id,
                r.question,
                r.expected_doc_id,
                to_json(e.expected_facts) AS expected_facts_json,
                to_json(r.retrieved_documents) AS retrieved_documents_json,
                r.hit_at_1,
                r.hit_at_3,
                r.reciprocal_rank,
                r.empty_retrieval
            FROM {retrieval_table} AS r
            INNER JOIN {evaluation_table} AS e
                ON r.query_id = e.query_id
            WHERE r.retrieval_run_id = ?
            ORDER BY r.query_id
            """,
            [retrieval_run_id],
        )

        rows = rows_as_dicts(cursor)

    if not rows:
        raise RuntimeError("No frozen RAG retrieval rows were found.")

    cases: list[EvaluationCase] = []

    for row in rows:
        expected_facts = json.loads(str(row["expected_facts_json"] or "[]"))

        retrieved_documents = json.loads(str(row["retrieved_documents_json"] or "[]"))

        cases.append(
            EvaluationCase(
                retrieval_run_id=str(row["retrieval_run_id"]),
                query_id=str(row["query_id"]),
                question=str(row["question"]),
                expected_doc_id=str(row["expected_doc_id"]),
                expected_facts=[str(fact) for fact in expected_facts],
                retrieved_documents=[dict(document) for document in retrieved_documents],
                hit_at_1=float(row["hit_at_1"]),
                hit_at_3=float(row["hit_at_3"]),
                reciprocal_rank=float(row["reciprocal_rank"]),
                empty_retrieval=bool(row["empty_retrieval"]),
            )
        )

    return cases


def build_documents(
    retrieved_documents: list[dict[str, Any]],
) -> list[Document]:
    """Convert frozen Delta retrieval rows into MLflow Documents."""

    documents: list[Document] = []

    for item in retrieved_documents:
        chunk_id = str(item.get("chunk_id") or "")
        doc_id = str(item.get("doc_id") or "")

        if not chunk_id:
            continue

        documents.append(
            Document(
                id=chunk_id,
                page_content=str(item.get("chunk_text") or ""),
                metadata={
                    "doc_uri": doc_id,
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "title": str(item.get("title") or ""),
                    "category": str(item.get("category") or ""),
                    "rank": int(item.get("rank") or 0),
                },
            )
        )

    return documents


def build_context(documents: list[Document]) -> str:
    """Create source-marked context from frozen MLflow Documents."""

    sections: list[str] = []

    for document in documents:
        metadata = document.metadata or {}
        chunk_id = str(metadata.get("chunk_id") or document.id or "unknown_chunk")
        title = str(metadata.get("title") or "Unknown source")
        category = str(metadata.get("category") or "unknown")

        sections.append(
            "\n".join(
                [
                    f"[SOURCE {chunk_id}]",
                    f"Title: {title}",
                    f"Category: {category}",
                    document.page_content,
                ]
            )
        )

    return "\n\n---\n\n".join(sections)


def extract_anthropic_text(response: Any) -> str:
    """Extract text blocks from an Anthropic Messages API response."""

    text_parts = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
        and isinstance(getattr(block, "text", None), str)
        and block.text.strip()
    ]

    answer = "\n".join(text_parts).strip()

    if not answer:
        raise RuntimeError("Anthropic returned no text response.")

    return answer


def require_metric(
    metrics: dict[str, Any],
    metric_name: str,
) -> float:
    """Read one required aggregate metric from MLflow GenAI evaluation."""

    value = metrics.get(metric_name)

    if value is None:
        raise RuntimeError(
            f"MLflow evaluation did not return required metric {metric_name!r}. Available metrics: {sorted(metrics)}"
        )

    return float(value)


def ensure_table_columns(
    connection,
    table_name: str,
    create_statement: str,
    required_columns: dict[str, str],
) -> None:
    """Create a Delta table and add newly introduced monitoring columns."""

    with connection.cursor() as cursor:
        cursor.execute(create_statement)

        cursor.execute(f"DESCRIBE TABLE {table_name}")
        rows = rows_as_dicts(cursor)

        existing = {
            str(row.get("col_name"))
            for row in rows
            if row.get("col_name") and not str(row.get("col_name")).startswith("#")
        }

        for column_name, sql_type in required_columns.items():
            if column_name in existing:
                continue

            cursor.execute(
                f"""
                ALTER TABLE {table_name}
                ADD COLUMNS ({column_name} {sql_type})
                """
            )


def insert_quality_history(
    connection,
    table_name: str,
    row: dict[str, Any],
) -> None:
    """Append one governed RAG quality-history row."""

    columns = list(row)
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)

    values = [row[column] for column in columns]

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {table_name}
            ({column_sql}, evaluated_at)
            VALUES ({placeholders}, current_timestamp())
            """,
            values,
        )


def replace_demo_rows(
    connection,
    table_name: str,
    rows: list[dict[str, Any]],
) -> None:
    """Replace the small governed demonstration-response table."""

    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {table_name}")

        if not rows:
            return

        columns = list(rows[0])
        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(columns)

        cursor.executemany(
            f"""
            INSERT INTO {table_name}
            ({column_sql}, generated_at)
            VALUES ({placeholders}, current_timestamp())
            """,
            [[row[column] for column in columns] for row in rows],
        )


def main() -> None:
    """Run the complete local M11 generation and evaluation stage."""

    args = parse_args()

    catalog = validate_identifier(
        args.catalog,
        "catalog",
    )

    anthropic_api_key = require_environment_variable("ANTHROPIC_API_KEY")
    openai_api_key = require_environment_variable("OPENAI_API_KEY")

    # MLflow predefined OpenAI judges resolve this environment variable.
    os.environ["OPENAI_API_KEY"] = openai_api_key

    # Ensure all Databricks-unified-auth consumers select the same workspace.
    os.environ["DATABRICKS_CONFIG_PROFILE"] = args.profile

    workspace = WorkspaceClient(
        profile=args.profile,
    )

    warehouse_id = choose_sql_warehouse(
        workspace,
        args.warehouse_id,
    )

    connection = databricks_sql_connection(
        args.profile,
        warehouse_id,
    )

    try:
        cases = load_frozen_evaluation_cases(
            connection,
            catalog,
        )

        retrieval_run_id = cases[0].retrieval_run_id

        print("Frozen retrieval run ID:", retrieval_run_id)
        print("Evaluation query count:", len(cases))

        cases_by_query_id = {case.query_id: case for case in cases}

        anthropic_client = Anthropic(api_key=anthropic_api_key)
        openai_client = OpenAI(api_key=openai_api_key)

        # ---------------------------------------------------------------
        # Provider connectivity smoke tests.
        # ---------------------------------------------------------------

        print("Running Anthropic local connectivity smoke test...")

        anthropic_smoke_started = time.perf_counter()

        anthropic_smoke_response = anthropic_client.messages.create(
            model=args.generation_model,
            messages=[
                {
                    "role": "user",
                    "content": ("Reply only with this exact text: EPIP_ANTHROPIC_READY"),
                }
            ],
            max_tokens=40,
        )

        anthropic_smoke_duration = time.perf_counter() - anthropic_smoke_started

        anthropic_smoke_text = extract_anthropic_text(anthropic_smoke_response)

        if "EPIP_ANTHROPIC_READY" not in anthropic_smoke_text:
            raise RuntimeError(f"Anthropic connectivity smoke test failed. Model: {args.generation_model}")

        print("Anthropic local connectivity: PASSED")

        print("Running OpenAI local connectivity smoke test...")

        openai_smoke_started = time.perf_counter()

        openai_smoke_response = openai_client.chat.completions.create(
            model=args.judge_model,
            messages=[
                {
                    "role": "user",
                    "content": ("Reply only with this exact text: EPIP_OPENAI_READY"),
                }
            ],
            max_tokens=40,
        )

        openai_smoke_duration = time.perf_counter() - openai_smoke_started

        if not openai_smoke_response.choices:
            raise RuntimeError("OpenAI connectivity smoke test returned no choices.")

        openai_smoke_text = openai_smoke_response.choices[0].message.content

        if not openai_smoke_text or "EPIP_OPENAI_READY" not in openai_smoke_text:
            raise RuntimeError(f"OpenAI connectivity smoke test failed. Model: {args.judge_model}")

        print("OpenAI local connectivity: PASSED")

        # ---------------------------------------------------------------
        # MLflow remote tracking in the PAYMENTS_DEV workspace.
        # ---------------------------------------------------------------

        mlflow.set_tracking_uri(f"databricks://{args.profile}")
        mlflow.set_experiment(args.experiment_name)

        # ---------------------------------------------------------------
        # Frozen retriever replay.
        # ---------------------------------------------------------------

        @mlflow.trace(span_type="RETRIEVER")
        def replay_validated_retrieval(
            query_id: str,
        ) -> list[Document]:
            """Replay the exact top-K documents from validation."""

            case = cases_by_query_id.get(query_id)

            if case is None:
                raise KeyError(f"Unknown evaluation query_id: {query_id}")

            return build_documents(case.retrieved_documents)

        @mlflow.trace(span_type="PARSER")
        def traced_build_context(
            documents: list[Document],
        ) -> str:
            """Build citation-aware context inside the MLflow trace."""

            return build_context(documents)

        @mlflow.trace(span_type="CHAT_MODEL")
        def generate_answer(
            question: str,
            context: str,
        ) -> str:
            """Generate evidence-grounded fraud-investigation guidance."""

            system_prompt = """
You are an enterprise payment fraud investigation assistant.

Your job is to help a fraud investigator understand what evidence should be
reviewed. You are not an autonomous fraud decision-maker.

You must answer only from the investigation knowledge supplied in the prompt.

Rules:

1. Treat fraud signals as investigation indicators, not definitive proof.
2. Distinguish observed evidence from possible interpretations.
3. Do not invent customers, transactions, merchants, policies, events,
   model scores, or evidence.
4. If the retrieved evidence is insufficient, explicitly state that
   additional investigation is required.
5. Cite factual guidance using the exact [SOURCE chunk_id] markers supplied
   in the retrieved context.
6. Do not invent source identifiers.
7. Prefer multiple independent signals over decisions based on one feature.
8. A fraud model score is an investigation aid, not definitive proof.
9. Keep the response concise and useful to a fraud investigator.
""".strip()

            user_prompt = f"""
INVESTIGATION QUESTION

{question}


RETRIEVED INVESTIGATION KNOWLEDGE

{context}


Respond using exactly these sections:

Assessment:
<brief evidence-based assessment>

Evidence to review:
<important indicators and supporting evidence>

Limitations:
<uncertainty, missing evidence, or why further investigation may be needed>

Sources:
<relevant [SOURCE chunk_id] citations>
""".strip()

            response = anthropic_client.messages.create(
                model=args.generation_model,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
                max_tokens=800,
            )

            return extract_anthropic_text(response)

        @mlflow.trace(span_type="CHAIN")
        def answer_question(
            query_id: str,
            question: str,
        ) -> str:
            """Execute RAG using the frozen formal retrieval result."""

            documents = replay_validated_retrieval(query_id)

            if not documents:
                return "No relevant investigation knowledge was retrieved. Additional investigation is required."

            context = traced_build_context(documents)

            return generate_answer(
                question=question,
                context=context,
            )

        # ---------------------------------------------------------------
        # Deterministic citation-validity scorer.
        # ---------------------------------------------------------------

        @scorer
        def valid_source_citations(
            outputs: str,
            trace: Trace,
        ) -> bool:
            """Require citations and reject every invented source ID."""

            if not isinstance(outputs, str):
                return False

            retriever_spans = trace.search_spans(span_type=SpanType.RETRIEVER)

            if not retriever_spans:
                return False

            retrieved_chunk_ids: set[str] = set()

            for retriever_span in retriever_spans:
                for document in retriever_span.outputs or []:
                    if isinstance(document, dict):
                        metadata = document.get("metadata", {}) or {}

                        chunk_id = metadata.get("chunk_id") or document.get("id")
                    else:
                        metadata = (
                            getattr(
                                document,
                                "metadata",
                                {},
                            )
                            or {}
                        )

                        chunk_id = metadata.get("chunk_id") or getattr(
                            document,
                            "id",
                            None,
                        )

                    if chunk_id:
                        retrieved_chunk_ids.add(str(chunk_id))

            if not retrieved_chunk_ids:
                return False

            cited_chunk_ids = set(
                re.findall(
                    r"\[SOURCE ([^\]]+)\]",
                    outputs,
                )
            )

            if not cited_chunk_ids:
                return False

            return cited_chunk_ids.issubset(retrieved_chunk_ids)

        evaluation_data = [
            {
                "inputs": {
                    "query_id": case.query_id,
                    "question": case.question,
                },
                "expectations": {
                    "expected_facts": case.expected_facts,
                },
                "tags": {
                    "query_id": case.query_id,
                    "expected_doc_id": case.expected_doc_id,
                    "retrieval_run_id": case.retrieval_run_id,
                    "epip_milestone": "11",
                    "use_case": "fraud_investigation_rag",
                    "execution_mode": "local_external_provider",
                },
            }
            for case in cases
        ]

        judge_model = f"openai:/{args.judge_model}"

        rag_scorers = [
            RetrievalRelevance(model=judge_model),
            RetrievalSufficiency(model=judge_model),
            RetrievalGroundedness(model=judge_model),
            RelevanceToQuery(model=judge_model),
            Safety(model=judge_model),
            valid_source_citations,
        ]

        print("Starting MLflow GenAI evaluation...")
        print("Generation model:", args.generation_model)
        print("Judge model:", judge_model)

        evaluation_started = time.perf_counter()

        evaluation_result = mlflow.genai.evaluate(
            data=evaluation_data,
            predict_fn=answer_question,
            scorers=rag_scorers,
        )

        evaluation_duration_seconds = time.perf_counter() - evaluation_started

        evaluation_run_id = evaluation_result.run_id
        evaluation_metrics = evaluation_result.metrics

        print("MLflow evaluation run ID:", evaluation_run_id)
        print(
            json.dumps(
                evaluation_metrics,
                indent=2,
                default=str,
            )
        )

        retrieval_relevance = require_metric(
            evaluation_metrics,
            "retrieval_relevance/mean",
        )
        retrieval_sufficiency = require_metric(
            evaluation_metrics,
            "retrieval_sufficiency/mean",
        )
        retrieval_groundedness = require_metric(
            evaluation_metrics,
            "retrieval_groundedness/mean",
        )
        answer_relevance = require_metric(
            evaluation_metrics,
            "relevance_to_query/mean",
        )
        safety_score = require_metric(
            evaluation_metrics,
            "safety/mean",
        )
        valid_citation_rate = require_metric(
            evaluation_metrics,
            "valid_source_citations/mean",
        )

        hit_at_1 = statistics.fmean(case.hit_at_1 for case in cases)
        recall_at_3 = statistics.fmean(case.hit_at_3 for case in cases)
        mean_reciprocal_rank = statistics.fmean(case.reciprocal_rank for case in cases)
        empty_retrieval_rate = statistics.fmean(float(case.empty_retrieval) for case in cases)

        quality_gates = {
            "hit_at_1": (hit_at_1 >= MIN_HIT_AT_1),
            "recall_at_3": (recall_at_3 >= MIN_RECALL_AT_3),
            "mean_reciprocal_rank": (mean_reciprocal_rank >= MIN_MRR),
            "empty_retrieval_rate": (empty_retrieval_rate <= MAX_EMPTY_RETRIEVAL_RATE),
            "retrieval_relevance": (retrieval_relevance >= MIN_RETRIEVAL_RELEVANCE),
            "retrieval_sufficiency": (retrieval_sufficiency >= MIN_RETRIEVAL_SUFFICIENCY),
            "retrieval_groundedness": (retrieval_groundedness >= MIN_GROUNDEDNESS),
            "answer_relevance": (answer_relevance >= MIN_ANSWER_RELEVANCE),
            "valid_citation_rate": (valid_citation_rate >= MIN_VALID_CITATION_RATE),
            "safety": (safety_score >= MIN_SAFETY),
        }

        failed_quality_gates = [gate_name for gate_name, passed in quality_gates.items() if not passed]

        quality_gate_status = "PASSED" if not failed_quality_gates else "FAILED"

        evaluation_query_count = len(cases)

        average_seconds_per_query = (
            evaluation_duration_seconds / evaluation_query_count if evaluation_query_count else 0.0
        )

        metrics_payload = {
            "deterministic_retrieval": {
                "hit_at_1": hit_at_1,
                "recall_at_3": recall_at_3,
                "mean_reciprocal_rank": mean_reciprocal_rank,
                "empty_retrieval_rate": empty_retrieval_rate,
            },
            "semantic_retrieval": {
                "retrieval_relevance": retrieval_relevance,
                "retrieval_sufficiency": retrieval_sufficiency,
            },
            "generation": {
                "retrieval_groundedness": retrieval_groundedness,
                "answer_relevance": answer_relevance,
                "valid_citation_rate": valid_citation_rate,
                "safety": safety_score,
            },
            "runtime": {
                "execution_mode": "local_external_provider",
                "evaluation_duration_seconds": evaluation_duration_seconds,
                "average_seconds_per_query": average_seconds_per_query,
                "anthropic_smoke_duration_seconds": anthropic_smoke_duration,
                "openai_smoke_duration_seconds": openai_smoke_duration,
            },
        }

        metrics_json = json.dumps(
            metrics_payload,
            sort_keys=True,
        )

        quality_table = f"{catalog}.ai.rag_quality_metrics"

        quality_columns = {
            "evaluation_run_id": "STRING",
            "retrieval_run_id": "STRING",
            "evaluation_query_count": "INT",
            "knowledge_index": "STRING",
            "retrieval_method": "STRING",
            "generation_provider": "STRING",
            "generation_model": "STRING",
            "judge_provider": "STRING",
            "judge_model": "STRING",
            "execution_mode": "STRING",
            "workspace_profile": "STRING",
            "hit_at_1": "DOUBLE",
            "recall_at_3": "DOUBLE",
            "mean_reciprocal_rank": "DOUBLE",
            "empty_retrieval_rate": "DOUBLE",
            "retrieval_relevance": "DOUBLE",
            "retrieval_sufficiency": "DOUBLE",
            "retrieval_groundedness": "DOUBLE",
            "answer_relevance": "DOUBLE",
            "valid_citation_rate": "DOUBLE",
            "safety_score": "DOUBLE",
            "evaluation_duration_seconds": "DOUBLE",
            "average_seconds_per_query": "DOUBLE",
            "quality_gate_status": "STRING",
            "failed_quality_gates": "STRING",
            "metrics_json": "STRING",
            "evaluated_at": "TIMESTAMP",
        }

        ensure_table_columns(
            connection,
            quality_table,
            f"""
            CREATE TABLE IF NOT EXISTS {quality_table} (
                evaluation_run_id STRING,
                retrieval_run_id STRING,
                evaluation_query_count INT,
                knowledge_index STRING,
                retrieval_method STRING,
                generation_provider STRING,
                generation_model STRING,
                judge_provider STRING,
                judge_model STRING,
                execution_mode STRING,
                workspace_profile STRING,
                hit_at_1 DOUBLE,
                recall_at_3 DOUBLE,
                mean_reciprocal_rank DOUBLE,
                empty_retrieval_rate DOUBLE,
                retrieval_relevance DOUBLE,
                retrieval_sufficiency DOUBLE,
                retrieval_groundedness DOUBLE,
                answer_relevance DOUBLE,
                valid_citation_rate DOUBLE,
                safety_score DOUBLE,
                evaluation_duration_seconds DOUBLE,
                average_seconds_per_query DOUBLE,
                quality_gate_status STRING,
                failed_quality_gates STRING,
                metrics_json STRING,
                evaluated_at TIMESTAMP
            )
            USING DELTA
            """,
            quality_columns,
        )

        quality_row = {
            "evaluation_run_id": evaluation_run_id,
            "retrieval_run_id": retrieval_run_id,
            "evaluation_query_count": evaluation_query_count,
            "knowledge_index": (f"{catalog}.ai.fraud_investigation_knowledge_index"),
            "retrieval_method": "HYBRID",
            "generation_provider": "anthropic",
            "generation_model": args.generation_model,
            "judge_provider": "openai",
            "judge_model": args.judge_model,
            "execution_mode": "local_external_provider",
            "workspace_profile": args.profile,
            "hit_at_1": hit_at_1,
            "recall_at_3": recall_at_3,
            "mean_reciprocal_rank": mean_reciprocal_rank,
            "empty_retrieval_rate": empty_retrieval_rate,
            "retrieval_relevance": retrieval_relevance,
            "retrieval_sufficiency": retrieval_sufficiency,
            "retrieval_groundedness": retrieval_groundedness,
            "answer_relevance": answer_relevance,
            "valid_citation_rate": valid_citation_rate,
            "safety_score": safety_score,
            "evaluation_duration_seconds": (float(evaluation_duration_seconds)),
            "average_seconds_per_query": (float(average_seconds_per_query)),
            "quality_gate_status": quality_gate_status,
            "failed_quality_gates": json.dumps(failed_quality_gates),
            "metrics_json": metrics_json,
        }

        insert_quality_history(
            connection,
            quality_table,
            quality_row,
        )

        # ---------------------------------------------------------------
        # Small governed demonstration set.
        #
        # Reuse frozen formal retrieval for three representative queries.
        # This keeps the demo deterministic and does not issue another
        # AI Search request.
        # ---------------------------------------------------------------

        demo_query_ids = [
            query_id
            for query_id in (
                "q001",
                "q005",
                "q010",
            )
            if query_id in cases_by_query_id
        ]

        demo_rows: list[dict[str, Any]] = []

        for query_id in demo_query_ids:
            case = cases_by_query_id[query_id]
            documents = build_documents(case.retrieved_documents)
            context = build_context(documents)

            demo_started = time.perf_counter()

            demo_answer = generate_answer(
                question=case.question,
                context=context,
            )

            demo_duration = time.perf_counter() - demo_started

            retrieved_chunk_ids = [
                str(
                    (document.metadata or {}).get(
                        "chunk_id",
                        document.id,
                    )
                )
                for document in documents
            ]

            retrieved_doc_ids = [
                str(
                    (document.metadata or {}).get(
                        "doc_id",
                        "",
                    )
                )
                for document in documents
            ]

            cited_chunk_ids = set(
                re.findall(
                    r"\[SOURCE ([^\]]+)\]",
                    demo_answer,
                )
            )

            contains_only_valid_source_citations = bool(cited_chunk_ids) and cited_chunk_ids.issubset(
                set(retrieved_chunk_ids)
            )

            demo_rows.append(
                {
                    "query_id": query_id,
                    "question": case.question,
                    "answer": demo_answer,
                    "retrieval_run_id": retrieval_run_id,
                    "retrieved_chunk_ids": json.dumps(retrieved_chunk_ids),
                    "retrieved_doc_ids": json.dumps(retrieved_doc_ids),
                    "retrieval_method": "HYBRID",
                    "generation_provider": "anthropic",
                    "generation_model": args.generation_model,
                    "evaluation_run_id": evaluation_run_id,
                    "execution_mode": "local_external_provider",
                    "contains_only_valid_source_citations": (contains_only_valid_source_citations),
                    "response_duration_seconds": (float(demo_duration)),
                }
            )

        demo_table = f"{catalog}.ai.rag_demo_responses"

        demo_columns = {
            "query_id": "STRING",
            "question": "STRING",
            "answer": "STRING",
            "retrieval_run_id": "STRING",
            "retrieved_chunk_ids": "STRING",
            "retrieved_doc_ids": "STRING",
            "retrieval_method": "STRING",
            "generation_provider": "STRING",
            "generation_model": "STRING",
            "evaluation_run_id": "STRING",
            "execution_mode": "STRING",
            "contains_only_valid_source_citations": "BOOLEAN",
            "response_duration_seconds": "DOUBLE",
            "generated_at": "TIMESTAMP",
        }

        ensure_table_columns(
            connection,
            demo_table,
            f"""
            CREATE TABLE IF NOT EXISTS {demo_table} (
                query_id STRING,
                question STRING,
                answer STRING,
                retrieval_run_id STRING,
                retrieved_chunk_ids STRING,
                retrieved_doc_ids STRING,
                retrieval_method STRING,
                generation_provider STRING,
                generation_model STRING,
                evaluation_run_id STRING,
                execution_mode STRING,
                contains_only_valid_source_citations BOOLEAN,
                response_duration_seconds DOUBLE,
                generated_at TIMESTAMP
            )
            USING DELTA
            """,
            demo_columns,
        )

        replace_demo_rows(
            connection,
            demo_table,
            demo_rows,
        )

        summary = {
            "evaluation_run_id": evaluation_run_id,
            "retrieval_run_id": retrieval_run_id,
            "evaluation_query_count": evaluation_query_count,
            "execution_mode": "local_external_provider",
            "generation": {
                "provider": "anthropic",
                "model": args.generation_model,
            },
            "judge": {
                "provider": "openai",
                "model": args.judge_model,
            },
            "retrieval": {
                "method": "HYBRID",
                "hit_at_1": hit_at_1,
                "recall_at_3": recall_at_3,
                "mean_reciprocal_rank": mean_reciprocal_rank,
                "empty_retrieval_rate": empty_retrieval_rate,
                "retrieval_relevance": retrieval_relevance,
                "retrieval_sufficiency": retrieval_sufficiency,
            },
            "generation_quality": {
                "groundedness": retrieval_groundedness,
                "answer_relevance": answer_relevance,
                "valid_citation_rate": valid_citation_rate,
                "safety": safety_score,
            },
            "quality_gate_status": quality_gate_status,
            "failed_quality_gates": failed_quality_gates,
        }

        print(
            json.dumps(
                summary,
                indent=2,
            )
        )

        if failed_quality_gates:
            raise RuntimeError(f"Milestone 11 RAG quality gates failed: {failed_quality_gates}")

        print("Milestone 11 RAG quality gates: PASSED")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
