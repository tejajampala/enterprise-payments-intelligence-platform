from pathlib import Path

import pytest
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest

from payments_intelligence.agents.contracts import (
    AgentRunResult,
    ToolExecutionRecord,
)
from payments_intelligence.agents.prompts import (
    SYSTEM_PROMPT,
    build_investigation_prompt,
)
from payments_intelligence.agents.responses_agent import (
    FraudInvestigationResponsesAgent,
)

ROOT = Path(__file__).resolve().parents[2]

PROMPTS_MODULE = ROOT / "src/payments_intelligence/agents/prompts.py"

CORE_MODULE = ROOT / "src/payments_intelligence/agents/fraud_investigation_agent.py"

RESPONSES_MODULE = ROOT / "src/payments_intelligence/agents/responses_agent.py"

RUNNER = ROOT / "scripts/agents/12_run_fraud_investigation_agent.py"


def _read(
    path: Path,
) -> str:
    """Read one repository source file."""

    return path.read_text(encoding="utf-8")


def test_m12b_runtime_files_exist() -> None:
    for path in (
        PROMPTS_MODULE,
        CORE_MODULE,
        RESPONSES_MODULE,
        RUNNER,
    ):
        assert path.exists(), str(path)


def test_system_prompt_enforces_human_review_and_read_only_role() -> None:
    prompt = SYSTEM_PROMPT.lower()

    assert "human review is required" in prompt

    assert "not an autonomous fraud decision engine" in prompt

    for forbidden_action in (
        "block a card",
        "freeze an account",
        "decline a payment",
        "update a fraud case",
    ):
        assert forbidden_action in prompt


def test_system_prompt_requires_final_investigation_structure() -> None:
    for heading in (
        "## Investigation Assessment",
        "## Risk Indicators",
        "## Counter-Indicators",
        "## Model Signal",
        "## Evidence Reviewed",
        "## Knowledge Sources",
        "## Limitations",
        "## Recommended Next Steps",
    ):
        assert heading in SYSTEM_PROMPT


def test_system_prompt_treats_model_signal_as_evidence_not_truth() -> None:
    prompt = SYSTEM_PROMPT.lower()

    assert "model score" in prompt or "model signal" in prompt

    assert "not proof" in prompt or "not independently establish" in prompt or "not definitively fraudulent" in prompt


def test_investigation_prompt_scopes_transaction() -> None:
    prompt = build_investigation_prompt(
        transaction_id=("txn-00000001"),
        investigator_question=("Review this payment."),
    )

    assert "txn-00000001" in prompt

    assert "exactly this transaction ID" in prompt


def test_core_implements_anthropic_client_tool_loop() -> None:
    source = _read(CORE_MODULE)

    assert "client.messages.create" in source

    assert "tool_use" in source

    assert "tool_result" in source

    assert "disable_parallel_tool_use" in source


def test_core_tracing_has_required_span_types() -> None:
    source = _read(CORE_MODULE)

    assert "SpanType.AGENT" in source

    assert "SpanType.CHAT_MODEL" in source

    assert "SpanType.TOOL" in source

    assert "SpanType.RETRIEVER" in source

    assert "mlflow.start_span" in source


def test_core_enforces_tool_call_limit() -> None:
    source = _read(CORE_MODULE)

    assert "self.settings.max_tool_calls" in source

    assert "TOOL_CALL_LIMIT_REACHED" in source


def test_core_detects_repeated_tool_calls() -> None:
    source = _read(CORE_MODULE)

    assert "seen_tool_signatures" in source

    assert "REPEATED_TOOL_CALL_BLOCKED" in source


def test_core_enforces_transaction_scope() -> None:
    source = _read(CORE_MODULE)

    assert "TRANSACTION_SCOPE_VIOLATION" in source

    assert "investigation_transaction_id" in source

    assert "requested_transaction_id" in source


def test_knowledge_search_is_traced_as_retriever() -> None:
    source = _read(CORE_MODULE)

    assert "SEARCH_FRAUD_KNOWLEDGE" in source

    assert "SpanType.RETRIEVER" in source

    assert "Document(" in source

    assert "doc_uri" in source


def test_responses_agent_subclasses_mlflow_responses_agent() -> None:
    assert issubclass(
        FraudInvestigationResponsesAgent,
        ResponsesAgent,
    )


def test_responses_agent_uses_untraced_core_under_mlflow_agent_trace() -> None:
    source = _read(RESPONSES_MODULE)

    # ResponsesAgent.predict() receives the MLflow AGENT
    # trace automatically, so it should call the untraced
    # core implementation.
    assert "self.core.run_investigation(" in source

    assert "run_investigation_traced(" not in source

    assert "create_function_call_item" in source

    assert "create_function_call_output_item" in source

    assert "create_text_output_item" in source


def test_responses_agent_extracts_latest_user_message() -> None:
    request = ResponsesAgentRequest(
        input=[
            {
                "role": "user",
                "content": ("First message"),
            },
            {
                "role": "assistant",
                "content": ("Acknowledged"),
            },
            {
                "role": "user",
                "content": ("Investigate txn-00000001"),
            },
        ]
    )

    result = FraudInvestigationResponsesAgent._latest_user_text(request)

    assert result == "Investigate txn-00000001"


def test_responses_agent_resolves_custom_transaction_scope() -> None:
    request = ResponsesAgentRequest(
        input=[
            {
                "role": "user",
                "content": ("Please investigate this payment"),
            }
        ],
        custom_inputs={"transaction_id": "txn-00000001"},
    )

    result = FraudInvestigationResponsesAgent._resolve_transaction_id(
        request=request,
        user_text=("Please investigate this payment"),
    )

    assert result == "txn-00000001"


def test_responses_agent_rejects_conflicting_transaction_scope() -> None:
    request = ResponsesAgentRequest(
        input=[
            {
                "role": "user",
                "content": ("Investigate txn-00000002"),
            }
        ],
        custom_inputs={"transaction_id": "txn-00000001"},
    )

    with pytest.raises(
        ValueError,
        match="conflict",
    ):
        (
            FraudInvestigationResponsesAgent._resolve_transaction_id(
                request=request,
                user_text=("Investigate txn-00000002"),
            )
        )


def test_agent_run_result_preserves_tool_trajectory() -> None:
    record = ToolExecutionRecord(
        tool_use_id="toolu_1",
        tool_name=("get_transaction_context"),
        arguments={"transaction_id": "txn-00000001"},
        result={
            "tool_name": "get_transaction_context",
            "ok": True,
        },
    )

    result = AgentRunResult(
        transaction_id=("txn-00000001"),
        final_text=("Human review is required."),
        generation_model=("claude-sonnet-4-6"),
        trace_id="tr-test",
        tool_calls=(record,),
    )

    assert result.tool_call_count == 1

    assert result.tools_used == ["get_transaction_context"]

    assert result.to_dict()["tool_calls"][0]["tool_use_id"] == "toolu_1"


def test_responses_agent_exposes_tool_trajectory() -> None:
    source = _read(RESPONSES_MODULE)

    assert "custom_outputs" in source

    assert '"transaction_id"' in source

    assert '"generation_model"' in source

    assert '"trace_id"' in source

    assert '"tool_call_count"' in source

    assert '"tools_used"' in source

    assert '"tool_calls"' in source

    assert "record.to_dict()" in source


def test_local_runner_tracks_to_databricks_and_supports_responses_interface() -> None:
    source = _read(RUNNER)

    # Do not assert exact Ruff formatting.
    assert "mlflow.set_tracking_uri" in source

    assert "databricks://" in source

    assert "args.profile" in source

    assert "/Shared/epip-dev-fraud-agent" in source

    assert "--interface" in source

    assert '"core"' in source

    assert '"responses"' in source

    assert "FraudInvestigationResponsesAgent" in source


def test_local_runner_supports_m12c_persistence() -> None:
    source = _read(RUNNER)

    assert "--no-persist" in source

    assert "DatabricksInvestigationPersistence" in source

    assert "build_persistence_record" in source

    assert "persistence.persist" in source


def test_local_runner_emits_m12c_ready_marker() -> None:
    source = _read(RUNNER)

    assert "EPIP_M12C_FRAUD_AGENT_READY" in source
