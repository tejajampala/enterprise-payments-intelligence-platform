"""MLflow ResponsesAgent adapter for the EPIP fraud-investigation core."""

from __future__ import annotations

import json
import re
from typing import Any
from uuid import uuid4

from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse

from payments_intelligence.agents.config import validate_transaction_id
from payments_intelligence.agents.fraud_investigation_agent import FraudInvestigationAgentCore

_TRANSACTION_REFERENCE_PATTERN = re.compile(r"\btxn-\d{8}\b")


class FraudInvestigationResponsesAgent(ResponsesAgent):
    """Expose the EPIP core through MLflow's standard ResponsesAgent contract."""

    def __init__(self, core: FraudInvestigationAgentCore) -> None:
        self.core = core

    @staticmethod
    def _as_dict(item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return item

        if hasattr(item, "model_dump"):
            return dict(item.model_dump(exclude_none=True))

        raise TypeError(f"Unsupported ResponsesAgent input item: {type(item)!r}")

    @classmethod
    def _latest_user_text(cls, request: ResponsesAgentRequest) -> str:
        """Extract the latest user text from Responses API compatible input."""

        for item in reversed(request.input):
            item_dict = cls._as_dict(item)

            if item_dict.get("role") != "user":
                continue

            content = item_dict.get("content")

            if isinstance(content, str) and content.strip():
                return content.strip()

            if isinstance(content, list):
                text_parts: list[str] = []

                for part in content:
                    part_dict = cls._as_dict(part) if not isinstance(part, dict) else part

                    if part_dict.get("type") == "input_text":
                        text = str(part_dict.get("text") or "").strip()

                        if text:
                            text_parts.append(text)

                if text_parts:
                    return "\n".join(text_parts)

        raise ValueError("ResponsesAgent request must contain a non-empty user message")

    @staticmethod
    def _resolve_transaction_id(
        request: ResponsesAgentRequest,
        user_text: str,
    ) -> str:
        """Resolve one transaction scope and reject conflicting transaction references."""

        custom_inputs = request.custom_inputs or {}
        explicit_transaction_id = custom_inputs.get("transaction_id")

        text_transaction_ids = set(_TRANSACTION_REFERENCE_PATTERN.findall(user_text))

        if explicit_transaction_id is not None:
            if not isinstance(explicit_transaction_id, str):
                raise ValueError("custom_inputs.transaction_id must be a string")

            transaction_id = validate_transaction_id(explicit_transaction_id)

            conflicting = {value for value in text_transaction_ids if value != transaction_id}

            if conflicting:
                raise ValueError(
                    "ResponsesAgent request contains transaction IDs that conflict with "
                    f"custom_inputs.transaction_id={transaction_id}: {sorted(conflicting)}"
                )

            return transaction_id

        if len(text_transaction_ids) != 1:
            raise ValueError(
                "Provide exactly one canonical transaction ID in the user message or custom_inputs.transaction_id"
            )

        return validate_transaction_id(next(iter(text_transaction_ids)))

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        """Run the core agent and return standard Responses API output items.

        MLflow automatically traces ResponsesAgent.predict() as an AGENT span. The core therefore
        uses its untraced run method here so CHAT_MODEL, TOOL, and RETRIEVER operations become
        children of this single AGENT root.
        """

        user_text = self._latest_user_text(request)
        transaction_id = self._resolve_transaction_id(
            request=request,
            user_text=user_text,
        )

        result = self.core.run_investigation(
            transaction_id=transaction_id,
            investigator_question=user_text,
        )

        output_items: list[Any] = []

        for record in result.tool_calls:
            output_items.append(
                self.create_function_call_item(
                    id=f"fc_{uuid4().hex[:12]}",
                    call_id=record.tool_use_id,
                    name=record.tool_name,
                    arguments=json.dumps(
                        record.arguments,
                        sort_keys=True,
                        default=str,
                    ),
                )
            )

            output_items.append(
                self.create_function_call_output_item(
                    call_id=record.tool_use_id,
                    output=json.dumps(
                        record.result,
                        sort_keys=True,
                        default=str,
                    ),
                )
            )

        output_items.append(
            self.create_text_output_item(
                text=result.final_text,
                id=f"msg_{uuid4().hex[:12]}",
            )
        )

        return ResponsesAgentResponse(
            output=output_items,
            custom_outputs={
                "transaction_id": result.transaction_id,
                "generation_model": result.generation_model,
                "trace_id": result.trace_id,
                "tool_call_count": result.tool_call_count,
                "tools_used": result.tools_used,
                "tool_calls": [record.to_dict() for record in result.tool_calls],
            },
        )
