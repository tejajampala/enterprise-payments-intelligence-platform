"""Typed contracts for EPIP fraud-investigation agent tools and runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """One ranked fraud-investigation knowledge chunk returned by AI Search."""

    rank: int
    chunk_id: str
    doc_id: str
    title: str
    category: str
    chunk_text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Framework-neutral definition of one tool exposed to an LLM."""

    name: str
    description: str
    input_schema: dict[str, Any]

    def to_anthropic_schema(self) -> dict[str, Any]:
        """Return the shape expected by Anthropic client tool calling."""

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "strict": True,
        }


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Normalized result returned by the M12 tool dispatcher."""

    tool_name: str
    ok: bool
    payload: dict[str, Any] | list[dict[str, Any]] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ToolExecutionRecord:
    """One model-requested tool call and the result returned to the model."""

    tool_use_id: str
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    repeated_call: bool = False
    scope_violation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    """Complete result of one fraud-investigation agent execution."""

    transaction_id: str
    final_text: str
    generation_model: str
    trace_id: str | None
    tool_calls: tuple[ToolExecutionRecord, ...]

    @property
    def tool_call_count(self) -> int:
        return len(self.tool_calls)

    @property
    def tools_used(self) -> list[str]:
        """Return unique tool names in first-use order."""

        ordered: list[str] = []

        for record in self.tool_calls:
            if record.tool_name not in ordered:
                ordered.append(record.tool_name)

        return ordered

    def to_dict(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "final_text": self.final_text,
            "generation_model": self.generation_model,
            "trace_id": self.trace_id,
            "tool_call_count": self.tool_call_count,
            "tools_used": self.tools_used,
            "tool_calls": [record.to_dict() for record in self.tool_calls],
        }
