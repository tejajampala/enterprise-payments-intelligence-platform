"""Governed Databricks data access for the EPIP fraud-investigation agent."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from databricks import sql
from databricks.ai_search.client import AISearchClient  # type: ignore[import-untyped]
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

from payments_intelligence.agents.config import (
    AgentSettings,
    validate_transaction_id,
)
from payments_intelligence.agents.contracts import (
    KnowledgeDocument,
)


class DatabricksAgentDataAccess:
    """Read-only adapter over UC functions, SQL Warehouse, and M11 AI Search."""

    def __init__(
        self,
        settings: AgentSettings,
        warehouse_id: str | None = None,
    ) -> None:
        """Initialize Databricks SQL and AI Search clients."""

        self.settings = settings
        self.workspace = WorkspaceClient(profile=settings.profile)
        self.warehouse_id = self._choose_sql_warehouse(warehouse_id)

        self.config = Config(
            profile=settings.profile,
            warehouse_id=self.warehouse_id,
        )

        headers = self.config.authenticate()
        authorization = headers.get("Authorization", "")

        if not authorization.startswith("Bearer "):
            raise RuntimeError("Databricks profile did not provide a Bearer authentication token")

        self._access_token = authorization.removeprefix("Bearer ").strip()

        if not self.config.sql_http_path:
            raise RuntimeError("Unable to determine SQL warehouse HTTP path")

        workspace_url = f"https://{self.config.hostname}"

        self._search_client = AISearchClient(
            workspace_url=workspace_url,
            personal_access_token=self._access_token,
            disable_notice=True,
        )

        self._search_index = self._search_client.get_index(
            endpoint_name=settings.search_endpoint_name,
            index_name=settings.knowledge_index_name,
        )

    def _choose_sql_warehouse(
        self,
        explicit_warehouse_id: str | None,
    ) -> str:
        """Choose the requested SQL warehouse or discover an available one."""

        if explicit_warehouse_id:
            return explicit_warehouse_id

        warehouses = list(self.workspace.warehouses.list())

        if not warehouses:
            raise RuntimeError("No Databricks SQL warehouse is available to the current user")

        running = [warehouse for warehouse in warehouses if "RUNNING" in str(getattr(warehouse, "state", "")).upper()]

        selected = running[0] if running else warehouses[0]
        selected_id = getattr(selected, "id", None)

        if not selected_id:
            raise RuntimeError("Unable to determine Databricks SQL warehouse ID")

        return str(selected_id)

    def _sql_connection(self) -> Any:
        """Open a SQL Connector session using Databricks unified authentication."""

        return sql.connect(
            server_hostname=self.config.hostname,
            http_path=self.config.sql_http_path,
            access_token=self._access_token,
            use_cloud_fetch=False,
            user_agent_entry="epip-m12-fraud-investigation-agent",
        )

    @staticmethod
    def _json_safe(value: Any) -> Any:
        """Normalize SQL result values so tool payloads are JSON serializable."""

        if isinstance(value, Decimal):
            return float(value)

        if isinstance(value, (datetime, date)):
            return value.isoformat()

        return value

    @classmethod
    def _rows_as_dicts(
        cls,
        cursor: Any,
    ) -> list[dict[str, Any]]:
        """Convert DB-API result rows into JSON-safe dictionaries."""

        if cursor.description is None:
            return []

        column_names = [description[0] for description in cursor.description]

        return [
            {
                column_name: cls._json_safe(value)
                for column_name, value in zip(
                    column_names,
                    row,
                    strict=False,
                )
            }
            for row in cursor.fetchall()
        ]

    def _query_rows(
        self,
        statement: str,
        parameters: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute one trusted read-only SELECT or CTE-based SELECT statement."""

        normalized = " ".join(statement.strip().upper().split())

        if not normalized:
            raise ValueError("SQL statement cannot be empty")

        if not normalized.startswith(("SELECT ", "WITH ")):
            raise ValueError("M12 agent data access only permits read-only SELECT statements")

        forbidden_pattern = re.compile(
            r"\b("
            r"DELETE|"
            r"INSERT|"
            r"MERGE|"
            r"UPDATE|"
            r"TRUNCATE|"
            r"DROP|"
            r"ALTER|"
            r"CREATE|"
            r"REPLACE|"
            r"GRANT|"
            r"REVOKE"
            r")\b",
            flags=re.IGNORECASE,
        )

        detected_forbidden = sorted({match.group(1).upper() for match in forbidden_pattern.finditer(normalized)})

        if detected_forbidden:
            raise ValueError(f"M12 agent data access rejected non-read-only SQL operation(s): {detected_forbidden}")

        with (
            self._sql_connection() as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                statement,
                parameters or [],
            )

            return self._rows_as_dicts(cursor)

    def find_sample_transaction_id(self) -> str:
        """Return one valid transaction ID for local agent smoke testing."""

        rows = self._query_rows(
            f"""
            SELECT
                transaction_id
            FROM
                {self.settings.transaction_context_view}
            ORDER BY
                transaction_id
            LIMIT 1
            """
        )

        if not rows:
            raise RuntimeError(f"No transactions are available in {self.settings.transaction_context_view}")

        return validate_transaction_id(str(rows[0]["transaction_id"]))

    def get_transaction_context(
        self,
        transaction_id: str,
    ) -> dict[str, Any] | None:
        """Execute the governed transaction-context Unity Catalog function."""

        transaction_id = validate_transaction_id(transaction_id)

        rows = self._query_rows(
            f"""
            SELECT *
            FROM
                {self.settings.transaction_context_function}(?)
            """,
            [transaction_id],
        )

        return rows[0] if rows else None

    def get_fraud_evidence(
        self,
        transaction_id: str,
    ) -> dict[str, Any] | None:
        """Execute the governed fraud-evidence Unity Catalog function."""

        transaction_id = validate_transaction_id(transaction_id)

        rows = self._query_rows(
            f"""
            SELECT *
            FROM
                {self.settings.fraud_evidence_function}(?)
            """,
            [transaction_id],
        )

        return rows[0] if rows else None

    @staticmethod
    def _parse_search_results(
        response: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Convert an AI Search response into ordered dictionaries."""

        manifest_columns = response.get("manifest", {}).get("columns", [])
        column_names = [str(column["name"]) for column in manifest_columns]

        result_rows = response.get("result", {}).get("data_array", []) or []

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

    def search_fraud_knowledge(
        self,
        question: str,
    ) -> list[dict[str, Any]]:
        """Run bounded HYBRID retrieval against the M11 fraud knowledge index."""

        normalized_question = question.strip()

        if not normalized_question:
            raise ValueError("Fraud-knowledge search question cannot be empty")

        if len(normalized_question) > self.settings.max_knowledge_query_characters:
            raise ValueError(
                "Fraud-knowledge search question "
                "exceeds the configured maximum of "
                f"{self.settings.max_knowledge_query_characters} "
                "characters"
            )

        response = self._search_index.similarity_search(
            query_text=normalized_question,
            columns=[
                "chunk_id",
                "doc_id",
                "title",
                "category",
                "chunk_text",
            ],
            num_results=self.settings.search_top_k,
            query_type="HYBRID",
        )

        records = self._parse_search_results(response)
        documents: list[KnowledgeDocument] = []

        for rank, record in enumerate(records, start=1):
            chunk_id = str(record.get("chunk_id") or "")

            if not chunk_id:
                continue

            documents.append(
                KnowledgeDocument(
                    rank=rank,
                    chunk_id=chunk_id,
                    doc_id=str(record.get("doc_id") or ""),
                    title=str(record.get("title") or ""),
                    category=str(record.get("category") or ""),
                    chunk_text=str(record.get("chunk_text") or ""),
                )
            )

        return [document.to_dict() for document in documents]
