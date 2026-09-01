"""Configuration and validation for EPIP fraud-investigation agents."""

from __future__ import annotations

import re
from dataclasses import dataclass

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_TRANSACTION_ID_PATTERN = re.compile(r"^txn-\d{8}$")


def validate_identifier(
    value: str,
    label: str,
) -> str:
    """Validate a simple Unity Catalog identifier."""

    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"Invalid {label}: {value!r}")

    return value


def validate_transaction_id(
    transaction_id: str,
) -> str:
    """Validate the canonical EPIP synthetic transaction identifier."""

    if not _TRANSACTION_ID_PATTERN.fullmatch(transaction_id):
        raise ValueError(
            f"Invalid transaction_id. Expected canonical EPIP format txn-########; received {transaction_id!r}."
        )

    return transaction_id


@dataclass(
    frozen=True,
    slots=True,
)
class AgentSettings:
    """Runtime settings shared by the M12 agent data and tool layers."""

    profile: str = "PAYMENTS_DEV"

    catalog: str = "payments_dev"

    ai_schema: str = "ai"

    search_endpoint_name: str = "epip-dev-fraud-knowledge-search"

    search_top_k: int = 3

    max_tool_calls: int = 6

    max_knowledge_query_characters: int = 2000

    def __post_init__(self) -> None:

        validate_identifier(
            self.catalog,
            "catalog",
        )

        validate_identifier(
            self.ai_schema,
            "ai_schema",
        )

        if not self.profile.strip():
            raise ValueError("Databricks profile cannot be empty")

        if not self.search_endpoint_name.strip():
            raise ValueError("AI Search endpoint name cannot be empty")

        if self.search_top_k < 1 or self.search_top_k > 3:
            raise ValueError("M12 search_top_k must be between 1 and 3")

        if self.max_tool_calls < 1 or self.max_tool_calls > 12:
            raise ValueError("max_tool_calls must be between 1 and 12")

        if self.max_knowledge_query_characters < 100:
            raise ValueError("max_knowledge_query_characters must be at least 100")

    @property
    def transaction_context_view(
        self,
    ) -> str:
        return f"{self.catalog}.{self.ai_schema}.agent_transaction_context"

    @property
    def fraud_evidence_view(
        self,
    ) -> str:
        return f"{self.catalog}.{self.ai_schema}.agent_fraud_evidence"

    @property
    def transaction_context_function(
        self,
    ) -> str:
        return f"{self.catalog}.{self.ai_schema}.get_transaction_context"

    @property
    def fraud_evidence_function(
        self,
    ) -> str:
        return f"{self.catalog}.{self.ai_schema}.get_fraud_evidence"

    @property
    def knowledge_index_name(
        self,
    ) -> str:
        return f"{self.catalog}.{self.ai_schema}.fraud_investigation_knowledge_index"
