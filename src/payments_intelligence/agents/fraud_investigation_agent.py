"""Claude tool-calling fraud-investigation agent for EPIP Milestone 12B."""

from __future__ import annotations

import json
from typing import Any

import mlflow
from anthropic import Anthropic
from mlflow.entities import Document, SpanType

from payments_intelligence.agents.config import AgentSettings, validate_transaction_id
from payments_intelligence.agents.contracts import (
    AgentRunResult,
    ToolExecutionRecord,
    ToolResult,
)
from payments_intelligence.agents.prompts import SYSTEM_PROMPT, build_investigation_prompt
from payments_intelligence.agents.tools import (
    GET_FRAUD_EVIDENCE,
    GET_TRANSACTION_CONTEXT,
    SEARCH_FRAUD_KNOWLEDGE,
    FraudInvestigationTools,
)

_STRUCTURED_TRANSACTION_TOOLS = {
    GET_TRANSACTION_CONTEXT,
    GET_FRAUD_EVIDENCE,
}


class FraudInvestigationAgentCore:
    """Pure-Python Claude agent that can use only the M12A allow-listed tools."""

    def __init__(
        self,
        settings: AgentSettings,
        tools: FraudInvestigationTools,
        generation_model: str = "claude-sonnet-4-6",
        max_tokens: int = 2200,
        anthropic_client: Anthropic | Any | None = None,
    ) -> None:
        if not generation_model.strip():
            raise ValueError("generation_model cannot be empty")

        if max_tokens < 256:
            raise ValueError("max_tokens must be at least 256")

        self.settings = settings
        self.tools = tools
        self.generation_model = generation_model
        self.max_tokens = max_tokens
        self.client = anthropic_client or Anthropic()

    @mlflow.trace(name="claude_tool_decision", span_type=SpanType.CHAT_MODEL)
    def _call_claude(
        self,
        messages: list[dict[str, Any]],
        allow_tools: bool,
    ) -> Any:
        """Call Claude once and trace the model turn."""

        span = mlflow.get_current_active_span()

        if span is not None:
            span.set_attributes(
                {
                    "ai.model.provider": "anthropic",
                    "ai.model.name": self.generation_model,
                    "epip.tools_enabled": allow_tools,
                }
            )

        request: dict[str, Any] = {
            "model": self.generation_model,
            "max_tokens": self.max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": messages,
            "tools": self.tools.anthropic_tool_schemas(),
            "tool_choice": (
                {
                    "type": "auto",
                    "disable_parallel_tool_use": True,
                }
                if allow_tools
                else {"type": "none"}
            ),
        }

        return self.client.messages.create(**request)

    @staticmethod
    def _tool_signature(
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """Return a deterministic signature for repeated-call detection."""

        return json.dumps(
            {
                "tool_name": tool_name,
                "arguments": arguments,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    @staticmethod
    def _text_from_response(response: Any) -> str:
        """Extract all final text blocks from one Anthropic response."""

        text_parts = [
            str(block.text).strip()
            for block in getattr(response, "content", [])
            if getattr(block, "type", None) == "text" and str(getattr(block, "text", "")).strip()
        ]

        return "\n".join(text_parts).strip()

    @staticmethod
    def _tool_use_blocks(response: Any) -> list[Any]:
        """Return client tool-use blocks from one Anthropic response."""

        return [block for block in getattr(response, "content", []) if getattr(block, "type", None) == "tool_use"]

    @staticmethod
    def _scope_violation_result(
        tool_name: str,
        investigation_transaction_id: str,
        requested_transaction_id: Any,
    ) -> ToolResult:
        return ToolResult(
            tool_name=tool_name,
            ok=False,
            error=(
                "TRANSACTION_SCOPE_VIOLATION: "
                f"investigation is scoped to {investigation_transaction_id}; "
                f"tool requested {requested_transaction_id!r}"
            ),
        )

    def _execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        investigation_transaction_id: str,
    ) -> dict[str, Any]:
        """Execute one tool under a TOOL or RETRIEVER child span."""

        span_type = SpanType.RETRIEVER if tool_name == SEARCH_FRAUD_KNOWLEDGE else SpanType.TOOL

        with mlflow.start_span(
            name=tool_name,
            span_type=span_type,
        ) as span:
            span.set_inputs(arguments)
            span.set_attributes(
                {
                    "epip.tool.name": tool_name,
                    "epip.transaction_id": investigation_transaction_id,
                }
            )

            if tool_name in _STRUCTURED_TRANSACTION_TOOLS:
                requested_transaction_id = arguments.get("transaction_id")

                if requested_transaction_id is not None and requested_transaction_id != investigation_transaction_id:
                    scoped_result = self._scope_violation_result(
                        tool_name=tool_name,
                        investigation_transaction_id=investigation_transaction_id,
                        requested_transaction_id=requested_transaction_id,
                    )
                    result_dict = scoped_result.to_dict()
                    span.set_outputs(result_dict)
                    span.set_attributes({"epip.scope_violation": True})
                    return result_dict

            result = self.tools.dispatch(
                tool_name=tool_name,
                arguments=arguments,
            )
            result_dict = result.to_dict()

            if tool_name == SEARCH_FRAUD_KNOWLEDGE and result.ok and isinstance(result.payload, list):
                documents = [
                    Document(
                        id=str(item.get("chunk_id") or ""),
                        page_content=str(item.get("chunk_text") or ""),
                        metadata={
                            "doc_uri": str(item.get("doc_id") or ""),
                            "doc_id": str(item.get("doc_id") or ""),
                            "chunk_id": str(item.get("chunk_id") or ""),
                            "title": str(item.get("title") or ""),
                            "category": str(item.get("category") or ""),
                            "rank": int(item.get("rank") or 0),
                        },
                    )
                    for item in result.payload
                    if str(item.get("chunk_id") or "")
                ]
                span.set_outputs(documents)
            else:
                span.set_outputs(result_dict)

            span.set_attributes({"epip.tool.ok": result.ok})
            return result_dict

    @staticmethod
    def _tool_result_block(
        tool_use_id: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Convert one normalized tool result to Anthropic's tool_result block."""

        block: dict[str, Any] = {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": json.dumps(result, default=str),
        }

        if not bool(result.get("ok")):
            block["is_error"] = True

        return block

    def run_investigation(
        self,
        transaction_id: str,
        investigator_question: str | None = None,
    ) -> AgentRunResult:
        """Run one tool-calling investigation inside an existing AGENT trace."""

        transaction_id = validate_transaction_id(transaction_id)
        prompt = build_investigation_prompt(
            transaction_id=transaction_id,
            investigator_question=investigator_question,
        )

        root_span = mlflow.get_current_active_span()

        if root_span is not None:
            root_span.set_attributes(
                {
                    "epip.transaction_id": transaction_id,
                    "epip.agent.version": "m12b-v1",
                    "epip.generation_model": self.generation_model,
                    "epip.max_tool_calls": self.settings.max_tool_calls,
                }
            )

        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": prompt,
            }
        ]

        tool_records: list[ToolExecutionRecord] = []
        seen_tool_signatures: set[str] = set()
        tool_call_count = 0

        response = self._call_claude(
            messages=messages,
            allow_tools=True,
        )

        while getattr(response, "stop_reason", None) == "tool_use":
            tool_blocks = self._tool_use_blocks(response)

            if not tool_blocks:
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": response.content,
                }
            )

            tool_result_blocks: list[dict[str, Any]] = []
            force_final_response = False

            for block in tool_blocks:
                tool_name = str(block.name)
                arguments = dict(block.input or {})
                tool_use_id = str(block.id)
                tool_call_count += 1

                signature = self._tool_signature(
                    tool_name=tool_name,
                    arguments=arguments,
                )
                repeated_call = signature in seen_tool_signatures
                scope_violation = False

                if tool_call_count > self.settings.max_tool_calls:
                    result = ToolResult(
                        tool_name=tool_name,
                        ok=False,
                        error=(
                            "TOOL_CALL_LIMIT_REACHED: "
                            f"maximum {self.settings.max_tool_calls} tool calls per investigation"
                        ),
                    ).to_dict()
                    force_final_response = True

                elif repeated_call:
                    result = ToolResult(
                        tool_name=tool_name,
                        ok=False,
                        error=(
                            "REPEATED_TOOL_CALL_BLOCKED: the same tool and arguments "
                            "were already executed in this investigation"
                        ),
                    ).to_dict()

                else:
                    seen_tool_signatures.add(signature)
                    result = self._execute_tool(
                        tool_name=tool_name,
                        arguments=arguments,
                        investigation_transaction_id=transaction_id,
                    )
                    scope_violation = str(result.get("error") or "").startswith("TRANSACTION_SCOPE_VIOLATION")

                tool_records.append(
                    ToolExecutionRecord(
                        tool_use_id=tool_use_id,
                        tool_name=tool_name,
                        arguments=arguments,
                        result=result,
                        repeated_call=repeated_call,
                        scope_violation=scope_violation,
                    )
                )

                tool_result_blocks.append(
                    self._tool_result_block(
                        tool_use_id=tool_use_id,
                        result=result,
                    )
                )

            messages.append(
                {
                    "role": "user",
                    "content": tool_result_blocks,
                }
            )

            response = self._call_claude(
                messages=messages,
                allow_tools=not force_final_response,
            )

            if force_final_response:
                break

        final_text = self._text_from_response(response)

        if not final_text:
            final_text = (
                "## Investigation Assessment\n"
                "The agent stopped before producing a complete evidence-based assessment. "
                "Human review is required.\n\n"
                "## Limitations\n"
                "No complete final model response was available.\n\n"
                "## Recommended Next Steps\n"
                "Review the collected tool evidence manually before taking any action."
            )

        trace_id = mlflow.get_active_trace_id()

        result = AgentRunResult(
            transaction_id=transaction_id,
            final_text=final_text,
            generation_model=self.generation_model,
            trace_id=trace_id,
            tool_calls=tuple(tool_records),
        )

        if root_span is not None:
            root_span.set_attributes(
                {
                    "epip.tool_call_count": result.tool_call_count,
                    "epip.tools_used": json.dumps(result.tools_used),
                }
            )
            root_span.set_outputs(result.to_dict())

        return result

    @mlflow.trace(name="fraud_investigation_agent", span_type=SpanType.AGENT)
    def run_investigation_traced(
        self,
        transaction_id: str,
        investigator_question: str | None = None,
    ) -> AgentRunResult:
        """Local-development entry point that creates the root AGENT trace."""

        return self.run_investigation(
            transaction_id=transaction_id,
            investigator_question=investigator_question,
        )
