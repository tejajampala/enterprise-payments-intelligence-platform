"""Typed contracts for EPIP Milestone 13 agent evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AgentEvaluationCase:
    """One governed golden investigation case."""

    case_id: str
    scenario_type: str
    transaction_id: str
    investigator_question: str
    required_tools: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    max_expected_tool_calls: int
    knowledge_required: bool
    citations_required: bool
    expected_behavior: str
    forbidden_behavior: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DeterministicScores:
    """Scores that do not require another language model."""

    tool_selection: float
    tool_arguments: float
    tool_efficiency: float
    scope_compliance: float
    structure: float
    citation: float
    human_review: float
    safety: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class JudgeScores:
    """Structured LLM-as-a-judge scores in the range 0..1."""

    groundedness: float
    evidence_completeness: float
    investigation_quality: float
    risk_balance: float
    uncertainty: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AgentEvaluationResult:
    """One complete M13 evaluation-case result."""

    evaluation_run_id: str
    case_id: str
    scenario_type: str
    transaction_id: str
    agent_version: str
    generation_model: str
    judge_model: str
    trace_id: str | None
    tools_used: tuple[str, ...]
    tool_call_count: int
    deterministic: DeterministicScores
    judge: JudgeScores
    duration_seconds: float
    overall_score: float
    case_pass: bool
    failure_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AgentEvaluationSummary:
    """Aggregate regression-gate result for one M13 evaluation run."""

    evaluation_run_id: str
    agent_version: str
    generation_model: str
    judge_model: str
    case_count: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    avg_tool_selection_score: float
    avg_tool_argument_score: float
    avg_tool_efficiency_score: float
    avg_groundedness_score: float
    avg_evidence_completeness_score: float
    avg_investigation_quality_score: float
    avg_citation_score: float
    scope_compliance_rate: float
    human_review_rate: float
    safety_rate: float
    structure_compliance_rate: float
    avg_duration_seconds: float
    overall_pass: bool
    failed_gates: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
