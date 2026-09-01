"""Approved read-only tools exposed to the EPIP fraud-investigation agent."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from payments_intelligence.agents.config import (
    validate_transaction_id,
)
from payments_intelligence.agents.contracts import (
    ToolDefinition,
    ToolResult,
)

GET_TRANSACTION_CONTEXT = "get_transaction_context"

GET_FRAUD_EVIDENCE = "get_fraud_evidence"

SEARCH_FRAUD_KNOWLEDGE = "search_fraud_knowledge"


class AgentDataAccess(Protocol):
    """Minimal data-access contract required by the tool dispatcher."""

    def get_transaction_context(
        self,
        transaction_id: str,
    ) -> dict[str, Any] | None: ...

    def get_fraud_evidence(
        self,
        transaction_id: str,
    ) -> dict[str, Any] | None: ...

    def search_fraud_knowledge(
        self,
        question: str,
    ) -> list[dict[str, Any]]: ...


TRANSACTION_CONTEXT_TOOL = ToolDefinition(
    name=(GET_TRANSACTION_CONTEXT),
    description=(
        "Retrieve governed investigation-time "
        "transaction, account, customer, and "
        "merchant context for one EPIP payment "
        "transaction. Use this when you need "
        "the basic facts of the payment. "
        "This tool is read-only and does not "
        "expose the final fraud investigation "
        "outcome."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "transaction_id": {
                "type": "string",
                "description": ("EPIP transaction ID in txn-######## format."),
            }
        },
        "required": ["transaction_id"],
        "additionalProperties": False,
    },
)


FRAUD_EVIDENCE_TOOL = ToolDefinition(
    name=(GET_FRAUD_EVIDENCE),
    description=(
        "Retrieve leakage-safe transaction, "
        "customer, and merchant behavioral "
        "features plus the Champion fraud-model "
        "signal for one transaction. Use this "
        "to understand risk indicators and "
        "historical behavior. A model score is "
        "evidence, not proof that a transaction "
        "is fraudulent."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "transaction_id": {
                "type": "string",
                "description": ("EPIP transaction ID in txn-######## format."),
            }
        },
        "required": ["transaction_id"],
        "additionalProperties": False,
    },
)


KNOWLEDGE_SEARCH_TOOL = ToolDefinition(
    name=(SEARCH_FRAUD_KNOWLEDGE),
    description=(
        "Search the governed EPIP "
        "fraud-investigation knowledge base "
        "using Databricks AI Search HYBRID "
        "retrieval. Use this when investigation "
        "guidance, fraud-pattern interpretation, "
        "or evidence-handling policy is needed. "
        "The tool returns at most three source "
        "chunks."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": ("Focused fraud-investigation knowledge question."),
            }
        },
        "required": ["question"],
        "additionalProperties": False,
    },
)


APPROVED_TOOL_DEFINITIONS = (
    TRANSACTION_CONTEXT_TOOL,
    FRAUD_EVIDENCE_TOOL,
    KNOWLEDGE_SEARCH_TOOL,
)

APPROVED_TOOL_NAMES = frozenset(definition.name for definition in APPROVED_TOOL_DEFINITIONS)


class FraudInvestigationTools:
    """Dispatcher for the small allow-listed set of M12 read-only tools."""

    def __init__(
        self,
        data_access: AgentDataAccess,
    ) -> None:

        self.data_access = data_access

    @staticmethod
    def anthropic_tool_schemas() -> list[dict[str, Any]]:
        """Return tool definitions ready for Anthropic tool calling in M12B."""

        return [definition.to_anthropic_schema() for definition in APPROVED_TOOL_DEFINITIONS]

    @staticmethod
    def _require_only(
        arguments: Mapping[str, Any],
        expected_key: str,
    ) -> Any:
        """Reject missing or extra model-supplied tool arguments."""

        keys = set(arguments)

        if keys != {expected_key}:
            raise ValueError(f"Expected exactly one tool argument {expected_key!r}; received {sorted(keys)}")

        return arguments[expected_key]

    def dispatch(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> ToolResult:
        """Execute one approved tool and normalize errors for the future agent loop."""

        if tool_name not in APPROVED_TOOL_NAMES:
            return ToolResult(
                tool_name=tool_name,
                ok=False,
                error=(f"UNKNOWN_TOOL: {tool_name}"),
            )

        try:
            if tool_name == GET_TRANSACTION_CONTEXT:
                raw_transaction_id = self._require_only(
                    arguments,
                    "transaction_id",
                )

                if not isinstance(
                    raw_transaction_id,
                    str,
                ):
                    raise ValueError("transaction_id must be a string")

                transaction_id = validate_transaction_id(raw_transaction_id)

                payload = self.data_access.get_transaction_context(transaction_id)

                if payload is None:
                    return ToolResult(
                        tool_name=tool_name,
                        ok=False,
                        error=(f"TRANSACTION_NOT_FOUND: {transaction_id}"),
                    )

                return ToolResult(
                    tool_name=tool_name,
                    ok=True,
                    payload=payload,
                )

            if tool_name == GET_FRAUD_EVIDENCE:
                raw_transaction_id = self._require_only(
                    arguments,
                    "transaction_id",
                )

                if not isinstance(
                    raw_transaction_id,
                    str,
                ):
                    raise ValueError("transaction_id must be a string")

                transaction_id = validate_transaction_id(raw_transaction_id)

                payload = self.data_access.get_fraud_evidence(transaction_id)

                if payload is None:
                    return ToolResult(
                        tool_name=tool_name,
                        ok=False,
                        error=(f"FRAUD_EVIDENCE_NOT_FOUND: {transaction_id}"),
                    )

                return ToolResult(
                    tool_name=tool_name,
                    ok=True,
                    payload=payload,
                )

            raw_question = self._require_only(
                arguments,
                "question",
            )

            if not isinstance(
                raw_question,
                str,
            ):
                raise ValueError("question must be a string")

            question = raw_question.strip()

            if not question:
                raise ValueError("question cannot be empty")

            documents = self.data_access.search_fraud_knowledge(question)

            if not documents:
                return ToolResult(
                    tool_name=tool_name,
                    ok=False,
                    error="KNOWLEDGE_NOT_FOUND",
                )

            return ToolResult(
                tool_name=tool_name,
                ok=True,
                payload=documents,
            )

        except Exception as exc:
            return ToolResult(
                tool_name=tool_name,
                ok=False,
                error=(f"{type(exc).__name__}: {exc}"),
            )
