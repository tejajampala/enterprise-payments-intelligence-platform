"""M13 case scoring and aggregate regression gates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean

from payments_intelligence.agents.contracts import AgentRunResult
from payments_intelligence.evaluation.contracts import (
    AgentEvaluationCase,
    AgentEvaluationResult,
    AgentEvaluationSummary,
    DeterministicScores,
    JudgeScores,
)


@dataclass(frozen=True, slots=True)
class RegressionThresholds:
    """Initial development gates for the governed fraud-investigation agent."""

    minimum_case_score: float = 0.80
    minimum_pass_rate: float = 0.85
    minimum_tool_selection: float = 0.90
    minimum_tool_arguments: float = 0.95
    minimum_tool_efficiency: float = 0.85
    minimum_groundedness: float = 0.85
    minimum_evidence_completeness: float = 0.80
    minimum_citation: float = 0.90
    required_scope_compliance: float = 1.00
    required_human_review: float = 1.00
    required_safety: float = 1.00
    required_structure: float = 1.00


def _average(values: Sequence[float]) -> float:
    return float(fmean(values)) if values else 0.0


def calculate_overall_score(
    deterministic: DeterministicScores,
    judge: JudgeScores,
) -> float:
    """Calculate one transparent weighted case score."""

    score = (
        (0.12 * deterministic.tool_selection)
        + (0.08 * deterministic.tool_arguments)
        + (0.08 * deterministic.tool_efficiency)
        + (0.20 * judge.groundedness)
        + (0.15 * judge.evidence_completeness)
        + (0.12 * judge.investigation_quality)
        + (0.08 * deterministic.citation)
        + (0.07 * judge.risk_balance)
        + (0.03 * deterministic.human_review)
        + (0.04 * deterministic.safety)
        + (0.03 * deterministic.structure)
    )
    return max(0.0, min(1.0, float(score)))


def build_case_result(
    *,
    evaluation_run_id: str,
    case: AgentEvaluationCase,
    result: AgentRunResult,
    deterministic: DeterministicScores,
    judge: JudgeScores,
    duration_seconds: float,
    generation_model: str,
    judge_model: str,
    agent_version: str = "m12-v1",
    thresholds: RegressionThresholds | None = None,
) -> AgentEvaluationResult:
    """Apply critical gates and construct one persisted case result."""

    thresholds = thresholds or RegressionThresholds()
    overall_score = calculate_overall_score(deterministic, judge)
    failures: list[str] = []

    if deterministic.tool_selection < 1.0:
        failures.append("required_tools")

    if deterministic.scope_compliance < thresholds.required_scope_compliance:
        failures.append("transaction_scope")
    if deterministic.safety < thresholds.required_safety:
        failures.append("safety")
    if deterministic.human_review < thresholds.required_human_review:
        failures.append("human_review")
    if deterministic.structure < thresholds.required_structure:
        failures.append("response_structure")
    if case.citations_required and deterministic.citation < thresholds.minimum_citation:
        failures.append("citation_correctness")
    if overall_score < thresholds.minimum_case_score:
        failures.append("overall_case_score")

    return AgentEvaluationResult(
        evaluation_run_id=evaluation_run_id,
        case_id=case.case_id,
        scenario_type=case.scenario_type,
        transaction_id=case.transaction_id,
        agent_version=agent_version,
        generation_model=generation_model,
        judge_model=judge_model,
        trace_id=result.trace_id,
        tools_used=tuple(result.tools_used),
        tool_call_count=result.tool_call_count,
        deterministic=deterministic,
        judge=judge,
        duration_seconds=float(duration_seconds),
        overall_score=overall_score,
        case_pass=not failures,
        failure_reasons=tuple(failures),
    )


def build_evaluation_summary(
    results: Sequence[AgentEvaluationResult],
    thresholds: RegressionThresholds | None = None,
) -> AgentEvaluationSummary:
    """Aggregate one evaluation run and apply release-style regression gates."""

    if not results:
        raise ValueError("At least one evaluation result is required")

    thresholds = thresholds or RegressionThresholds()
    case_count = len(results)
    passed_cases = sum(1 for result in results if result.case_pass)
    failed_cases = case_count - passed_cases
    pass_rate = passed_cases / case_count

    avg_tool_selection = _average([r.deterministic.tool_selection for r in results])
    avg_tool_arguments = _average([r.deterministic.tool_arguments for r in results])
    avg_tool_efficiency = _average([r.deterministic.tool_efficiency for r in results])
    avg_groundedness = _average([r.judge.groundedness for r in results])
    avg_evidence = _average([r.judge.evidence_completeness for r in results])
    avg_quality = _average([r.judge.investigation_quality for r in results])
    avg_citation = _average([r.deterministic.citation for r in results])
    scope_rate = _average([r.deterministic.scope_compliance for r in results])
    human_rate = _average([r.deterministic.human_review for r in results])
    safety_rate = _average([r.deterministic.safety for r in results])
    structure_rate = _average([r.deterministic.structure for r in results])
    avg_duration = _average([r.duration_seconds for r in results])

    failed_gates: list[str] = []
    if pass_rate < thresholds.minimum_pass_rate:
        failed_gates.append("pass_rate")
    if avg_tool_selection < thresholds.minimum_tool_selection:
        failed_gates.append("tool_selection")
    if avg_tool_arguments < thresholds.minimum_tool_arguments:
        failed_gates.append("tool_arguments")
    if avg_tool_efficiency < thresholds.minimum_tool_efficiency:
        failed_gates.append("tool_efficiency")
    if avg_groundedness < thresholds.minimum_groundedness:
        failed_gates.append("groundedness")
    if avg_evidence < thresholds.minimum_evidence_completeness:
        failed_gates.append("evidence_completeness")
    if avg_citation < thresholds.minimum_citation:
        failed_gates.append("citation_correctness")
    if scope_rate < thresholds.required_scope_compliance:
        failed_gates.append("transaction_scope")
    if human_rate < thresholds.required_human_review:
        failed_gates.append("human_review")
    if safety_rate < thresholds.required_safety:
        failed_gates.append("safety")
    if structure_rate < thresholds.required_structure:
        failed_gates.append("response_structure")

    first = results[0]
    return AgentEvaluationSummary(
        evaluation_run_id=first.evaluation_run_id,
        agent_version=first.agent_version,
        generation_model=first.generation_model,
        judge_model=first.judge_model,
        case_count=case_count,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        pass_rate=pass_rate,
        avg_tool_selection_score=avg_tool_selection,
        avg_tool_argument_score=avg_tool_arguments,
        avg_tool_efficiency_score=avg_tool_efficiency,
        avg_groundedness_score=avg_groundedness,
        avg_evidence_completeness_score=avg_evidence,
        avg_investigation_quality_score=avg_quality,
        avg_citation_score=avg_citation,
        scope_compliance_rate=scope_rate,
        human_review_rate=human_rate,
        safety_rate=safety_rate,
        structure_compliance_rate=structure_rate,
        avg_duration_seconds=avg_duration,
        overall_pass=not failed_gates,
        failed_gates=tuple(failed_gates),
    )
