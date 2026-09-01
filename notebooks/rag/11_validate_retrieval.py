# Databricks notebook source

"""Milestone 11 — Validate fraud-investigation AI Search retrieval quality.

This notebook performs the formal retrieval stage once and persists the exact
retrieved top-K documents. The local RAG-quality runner replays these frozen results so deterministic
retrieval metrics and LLM judges evaluate the exact same context.

Metrics:
- Hit@1
- Recall@3 (equivalent to Hit@3 for the current one-relevant-document dataset)
- Mean Reciprocal Rank (MRR)
- Empty retrieval rate
"""

# COMMAND ----------

from typing import Any
from uuid import uuid4

from databricks.ai_search.client import AISearchClient
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

# COMMAND ----------
# Spark session.

spark_session = SparkSession.getActiveSession()

if spark_session is None:
    raise RuntimeError("No active SparkSession is available for retrieval validation")

# COMMAND ----------
# Runtime configuration.

dbutils.widgets.text("catalog_name", "payments_dev")
dbutils.widgets.text("search_endpoint_name", "epip-dev-fraud-knowledge-search")

CATALOG = dbutils.widgets.get("catalog_name")
SEARCH_ENDPOINT_NAME = dbutils.widgets.get("search_endpoint_name")

INDEX_NAME = f"{CATALOG}.ai.fraud_investigation_knowledge_index"
EVALUATION_DATASET_TABLE = f"{CATALOG}.ai.rag_evaluation_dataset"
RETRIEVAL_RESULTS_TABLE = f"{CATALOG}.ai.rag_retrieval_evaluation"

TOP_K = 3
RETRIEVAL_METHOD = "HYBRID"

# COMMAND ----------
# EPIP development quality gates.

MIN_HIT_AT_1 = 0.60
MIN_RECALL_AT_3 = 0.80
MIN_MRR = 0.65
MAX_EMPTY_RETRIEVAL_RATE = 0.0

# COMMAND ----------
# AI Search client.

search_client = AISearchClient()
search_index = search_client.get_index(
    endpoint_name=SEARCH_ENDPOINT_NAME,
    index_name=INDEX_NAME,
)

# One identifier ties every row from this formal retrieval execution together.
retrieval_run_id = str(uuid4())

print("Retrieval run ID:", retrieval_run_id)
print("AI Search endpoint:", SEARCH_ENDPOINT_NAME)
print("AI Search index:", INDEX_NAME)
print("Retrieval method:", RETRIEVAL_METHOD)
print("Top K:", TOP_K)

# COMMAND ----------
# AI Search response parser.


def parse_search_results(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert an AI Search response into ordered dictionaries."""

    manifest_columns = response.get("manifest", {}).get("columns", [])

    column_names = [column["name"] for column in manifest_columns]

    result_rows = response.get("result", {}).get("data_array", [])

    return [
        {
            column_name: value
            for column_name, value in zip(
                column_names,
                row,
                strict=False,
            )
        }
        for row in result_rows
    ]


# COMMAND ----------
# Load the governed golden evaluation dataset.

required_evaluation_columns = {
    "query_id",
    "question",
    "expected_doc_id",
}

evaluation_df = spark_session.table(EVALUATION_DATASET_TABLE)
missing_evaluation_columns = required_evaluation_columns.difference(evaluation_df.columns)

if missing_evaluation_columns:
    raise ValueError(f"RAG evaluation dataset is missing required columns: {sorted(missing_evaluation_columns)}")

evaluation_rows = evaluation_df.select("query_id", "question", "expected_doc_id").orderBy("query_id").collect()

if not evaluation_rows:
    raise ValueError("RAG evaluation dataset is empty")

print("Evaluation query count:", len(evaluation_rows))

# COMMAND ----------
# Execute the one formal retrieval pass.

retrieval_results: list[dict[str, Any]] = []

for evaluation_row in evaluation_rows:
    query_id = str(evaluation_row["query_id"])
    question = str(evaluation_row["question"])
    expected_doc_id = str(evaluation_row["expected_doc_id"])

    response = search_index.similarity_search(
        query_text=question,
        columns=[
            "chunk_id",
            "doc_id",
            "title",
            "category",
            "chunk_text",
        ],
        num_results=TOP_K,
        query_type=RETRIEVAL_METHOD,
    )

    retrieved_records = parse_search_results(response)

    retrieved_documents: list[dict[str, Any]] = []

    for rank, record in enumerate(retrieved_records, start=1):
        retrieved_documents.append(
            {
                "rank": rank,
                "chunk_id": str(record.get("chunk_id") or ""),
                "doc_id": str(record.get("doc_id") or ""),
                "title": str(record.get("title") or ""),
                "category": str(record.get("category") or ""),
                "chunk_text": str(record.get("chunk_text") or ""),
            }
        )

    retrieved_doc_ids = [document["doc_id"] for document in retrieved_documents if document["doc_id"]]

    retrieved_chunk_ids = [document["chunk_id"] for document in retrieved_documents if document["chunk_id"]]

    empty_retrieval = len(retrieved_documents) == 0

    expected_rank = None

    for rank, retrieved_doc_id in enumerate(retrieved_doc_ids, start=1):
        if retrieved_doc_id == expected_doc_id:
            expected_rank = rank
            break

    hit_at_1 = int(expected_rank == 1)

    # The current EPIP golden dataset has exactly one expected relevant document
    # per query. Therefore Hit@3 is equivalent to per-query Recall@3.
    hit_at_3 = int(expected_rank is not None and expected_rank <= TOP_K)

    reciprocal_rank = 1.0 / float(expected_rank) if expected_rank is not None else 0.0

    retrieval_results.append(
        {
            "retrieval_run_id": retrieval_run_id,
            "query_id": query_id,
            "question": question,
            "expected_doc_id": expected_doc_id,
            "search_endpoint_name": SEARCH_ENDPOINT_NAME,
            "index_name": INDEX_NAME,
            "retrieval_method": RETRIEVAL_METHOD,
            "top_k": TOP_K,
            "retrieved_documents": retrieved_documents,
            "retrieved_doc_ids": retrieved_doc_ids,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "expected_rank": expected_rank,
            "hit_at_1": hit_at_1,
            "hit_at_3": hit_at_3,
            "reciprocal_rank": reciprocal_rank,
            "empty_retrieval": empty_retrieval,
        }
    )

# COMMAND ----------
# Explicit Spark schema.

retrieved_document_schema = StructType(
    [
        StructField("rank", IntegerType(), False),
        StructField("chunk_id", StringType(), False),
        StructField("doc_id", StringType(), False),
        StructField("title", StringType(), False),
        StructField("category", StringType(), False),
        StructField("chunk_text", StringType(), False),
    ]
)

retrieval_results_schema = StructType(
    [
        StructField("retrieval_run_id", StringType(), False),
        StructField("query_id", StringType(), False),
        StructField("question", StringType(), False),
        StructField("expected_doc_id", StringType(), False),
        StructField("search_endpoint_name", StringType(), False),
        StructField("index_name", StringType(), False),
        StructField("retrieval_method", StringType(), False),
        StructField("top_k", IntegerType(), False),
        StructField(
            "retrieved_documents",
            ArrayType(retrieved_document_schema, containsNull=False),
            False,
        ),
        StructField("retrieved_doc_ids", ArrayType(StringType()), False),
        StructField("retrieved_chunk_ids", ArrayType(StringType()), False),
        StructField("expected_rank", IntegerType(), True),
        StructField("hit_at_1", IntegerType(), False),
        StructField("hit_at_3", IntegerType(), False),
        StructField("reciprocal_rank", DoubleType(), False),
        StructField("empty_retrieval", BooleanType(), False),
    ]
)

# COMMAND ----------
# Persist exact retrieval results for the local M11 evaluation runner.

retrieval_results_df = spark_session.createDataFrame(
    retrieval_results,
    schema=retrieval_results_schema,
).withColumn("evaluated_at", F.current_timestamp())

(
    retrieval_results_df.write.format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(RETRIEVAL_RESULTS_TABLE)
)

print("Retrieval evaluation written to:", RETRIEVAL_RESULTS_TABLE)

# COMMAND ----------
# Aggregate deterministic metrics.

metric_row = retrieval_results_df.agg(
    F.avg(F.col("hit_at_1").cast("double")).alias("hit_at_1"),
    F.avg(F.col("hit_at_3").cast("double")).alias("recall_at_3"),
    F.avg(F.col("reciprocal_rank")).alias("mean_reciprocal_rank"),
    F.avg(F.col("empty_retrieval").cast("double")).alias("empty_retrieval_rate"),
).first()

if metric_row is None:
    raise RuntimeError("Unable to calculate retrieval metrics")

hit_at_1 = float(metric_row["hit_at_1"])
recall_at_3 = float(metric_row["recall_at_3"])
mean_reciprocal_rank = float(metric_row["mean_reciprocal_rank"])
empty_retrieval_rate = float(metric_row["empty_retrieval_rate"])

# COMMAND ----------
# Display per-query results.

display(
    retrieval_results_df.select(
        "retrieval_run_id",
        "query_id",
        "question",
        "expected_doc_id",
        "retrieved_doc_ids",
        "retrieved_chunk_ids",
        "expected_rank",
        "hit_at_1",
        "hit_at_3",
        "reciprocal_rank",
        "empty_retrieval",
        "evaluated_at",
    ).orderBy("query_id")
)

# COMMAND ----------
# Aggregate metric summary.

print("Deterministic retrieval metrics")
print(f"Hit@1: {hit_at_1:.4f}")
print(f"Recall@3: {recall_at_3:.4f}")
print(f"Mean Reciprocal Rank: {mean_reciprocal_rank:.4f}")
print(f"Empty retrieval rate: {empty_retrieval_rate:.4f}")

# COMMAND ----------
# Retrieval quality gates.

retrieval_quality_gates = {
    "hit_at_1": hit_at_1 >= MIN_HIT_AT_1,
    "recall_at_3": recall_at_3 >= MIN_RECALL_AT_3,
    "mean_reciprocal_rank": mean_reciprocal_rank >= MIN_MRR,
    "empty_retrieval_rate": (empty_retrieval_rate <= MAX_EMPTY_RETRIEVAL_RATE),
}

failed_retrieval_quality_gates = [gate_name for gate_name, passed in retrieval_quality_gates.items() if not passed]

print("Retrieval quality gates:")
for gate_name, passed in retrieval_quality_gates.items():
    print(gate_name, "PASSED" if passed else "FAILED")

if failed_retrieval_quality_gates:
    raise ValueError(f"Deterministic retrieval quality gates failed: {failed_retrieval_quality_gates}")

print("Deterministic retrieval quality gates: PASSED")
