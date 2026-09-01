# Databricks notebook source

"""Milestone 11 — Create/synchronize the fraud-investigation AI Search index.

The AI Search endpoint itself is managed by the Databricks bundle.
This notebook creates the triggered Delta Sync index after the governed source
Delta table exists, synchronizes an existing index, waits for readiness, and
runs a HYBRID retrieval smoke test.
"""

# COMMAND ----------

import json
import time
from typing import Any

from databricks.ai_search.client import AISearchClient
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

# COMMAND ----------
# Spark session.

spark_session = SparkSession.getActiveSession()

if spark_session is None:
    raise RuntimeError("No active SparkSession is available for AI Search setup")

# COMMAND ----------
# Runtime configuration.

dbutils.widgets.text("catalog_name", "payments_dev")
dbutils.widgets.text("search_endpoint_name", "epip-dev-fraud-knowledge-search")
dbutils.widgets.text("embedding_model_endpoint", "databricks-qwen3-embedding-0-6b")

CATALOG = dbutils.widgets.get("catalog_name")
SEARCH_ENDPOINT_NAME = dbutils.widgets.get("search_endpoint_name")
EMBEDDING_MODEL_ENDPOINT = dbutils.widgets.get("embedding_model_endpoint")

SOURCE_TABLE = f"{CATALOG}.ai.fraud_investigation_knowledge_chunks"
INDEX_NAME = f"{CATALOG}.ai.fraud_investigation_knowledge_index"

REQUIRED_SOURCE_COLUMNS = {
    "chunk_id",
    "doc_id",
    "title",
    "category",
    "chunk_text",
}

# COMMAND ----------
# Validate source table.

source_df = spark_session.table(SOURCE_TABLE)
source_count = source_df.count()

if source_count == 0:
    raise ValueError(f"AI Search source table is empty: {SOURCE_TABLE}")

missing_columns = REQUIRED_SOURCE_COLUMNS.difference(source_df.columns)
if missing_columns:
    raise ValueError(f"AI Search source table is missing required columns: {sorted(missing_columns)}")

null_primary_key_count = source_df.filter(F.col("chunk_id").isNull()).count()
if null_primary_key_count:
    raise ValueError(f"AI Search source table contains {null_primary_key_count} null chunk_id values")

duplicate_primary_key_count = source_df.groupBy("chunk_id").count().filter(F.col("count") > 1).count()

if duplicate_primary_key_count:
    raise ValueError(
        f"AI Search source table contains duplicate chunk_id values: {duplicate_primary_key_count} duplicate keys"
    )

properties = {
    row["key"]: row["value"]
    for row in spark_session.sql(
        f"""
        SHOW TBLPROPERTIES {SOURCE_TABLE}
        """
    ).collect()
}

if properties.get("delta.enableChangeDataFeed") != "true":
    raise ValueError("AI Search source table must have Delta Change Data Feed enabled")

print(f"Validated AI Search source table: {SOURCE_TABLE}")
print(f"Source rows: {source_count}")

# COMMAND ----------
# AI Search client.
#
# In Databricks notebook/job execution, authentication is auto-detected.

client = AISearchClient()

# COMMAND ----------
# Helper functions.


def get_endpoint_state(endpoint_payload: dict[str, Any]) -> str:
    """Extract the endpoint state from the SDK response."""

    endpoint_status = endpoint_payload.get("endpoint_status", {}) or {}
    return str(endpoint_status.get("state") or "UNKNOWN")


def index_is_ready(index_description: dict[str, Any]) -> bool:
    """Handle both current and older SDK readiness fields."""

    status = index_description.get("status", {}) or {}

    if bool(status.get("ready", False)):
        return True

    detailed_state = str(status.get("detailed_state") or "")
    return detailed_state.startswith("ONLINE")


def index_status_text(index_description: dict[str, Any]) -> str:
    """Return a readable index status for logs."""

    status = index_description.get("status", {}) or {}
    return str(status.get("detailed_state") or status.get("message") or status.get("status") or "UNKNOWN")


# COMMAND ----------
# Wait for bundle-managed endpoint to become ONLINE.

ENDPOINT_TIMEOUT_SECONDS = 1200
ENDPOINT_POLL_SECONDS = 15
endpoint_started = time.monotonic()

while True:
    endpoint = client.get_endpoint(name=SEARCH_ENDPOINT_NAME)
    endpoint_state = get_endpoint_state(endpoint)

    print(f"AI Search endpoint state: {endpoint_state}")

    if endpoint_state == "ONLINE":
        break

    if endpoint_state in {
        "OFFLINE",
        "RED_STATE",
        "DELETED",
        "FAILED",
    }:
        raise RuntimeError(f"AI Search endpoint entered an unexpected state: {endpoint_state}")

    if time.monotonic() - endpoint_started > ENDPOINT_TIMEOUT_SECONDS:
        raise TimeoutError("AI Search endpoint did not become ONLINE within the timeout")

    time.sleep(ENDPOINT_POLL_SECONDS)

# COMMAND ----------
# Determine whether the index already exists.

index = None

try:
    index = client.get_index(
        endpoint_name=SEARCH_ENDPOINT_NAME,
        index_name=INDEX_NAME,
    )
    print(f"Existing AI Search index found: {INDEX_NAME}")
except Exception as exc:
    error_message = str(exc).lower()
    not_found_markers = (
        "not found",
        "does not exist",
        "resource_does_not_exist",
        "resource does not exist",
        "404",
    )

    if not any(marker in error_message for marker in not_found_markers):
        raise

# COMMAND ----------
# Create triggered Delta Sync index when missing; otherwise synchronize it.

if index is None:
    print(f"Creating AI Search index: {INDEX_NAME}")

    index = client.create_delta_sync_index(
        endpoint_name=SEARCH_ENDPOINT_NAME,
        source_table_name=SOURCE_TABLE,
        index_name=INDEX_NAME,
        pipeline_type="TRIGGERED",
        primary_key="chunk_id",
        embedding_source_column="chunk_text",
        embedding_model_endpoint_name=EMBEDDING_MODEL_ENDPOINT,
    )
else:
    print("Triggering Delta Sync for existing AI Search index")
    index.sync()

# COMMAND ----------
# Wait until the index is ready / online.

INDEX_TIMEOUT_SECONDS = 1800
INDEX_POLL_SECONDS = 20
index_started = time.monotonic()

while True:
    index = client.get_index(
        endpoint_name=SEARCH_ENDPOINT_NAME,
        index_name=INDEX_NAME,
    )

    index_description = index.describe()
    status_text = index_status_text(index_description)

    print("AI Search index status:", status_text)

    if index_is_ready(index_description):
        break

    normalized_status = status_text.upper()
    if any(failure_marker in normalized_status for failure_marker in ("FAILED", "ERROR", "RED_STATE")):
        raise RuntimeError(f"AI Search index entered a failure state: {status_text}")

    if time.monotonic() - index_started > INDEX_TIMEOUT_SECONDS:
        raise TimeoutError("AI Search index did not become ready within the timeout")

    time.sleep(INDEX_POLL_SECONDS)

# COMMAND ----------
# Hybrid retrieval smoke test.

smoke_test = index.similarity_search(
    query_text="How should card not present fraud be investigated?",
    columns=[
        "chunk_id",
        "doc_id",
        "title",
        "category",
        "chunk_text",
    ],
    num_results=3,
    query_type="HYBRID",
)

result_block = smoke_test.get("result", {}) or {}
data_array = result_block.get("data_array", []) or []
row_count = int(result_block.get("row_count", len(data_array)))

if row_count == 0:
    raise RuntimeError("AI Search hybrid smoke test returned no results")

# COMMAND ----------
# Final summary.

print(
    json.dumps(
        {
            "endpoint": SEARCH_ENDPOINT_NAME,
            "index": INDEX_NAME,
            "source_table": SOURCE_TABLE,
            "source_rows": source_count,
            "embedding_model": EMBEDDING_MODEL_ENDPOINT,
            "pipeline_type": "TRIGGERED",
            "retrieval_method": "HYBRID",
            "smoke_test_result_count": row_count,
        },
        indent=2,
    )
)
