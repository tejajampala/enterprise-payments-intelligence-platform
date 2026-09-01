from pathlib import Path
from typing import Any

import yaml

from payments_intelligence.agents.contracts import (
    AgentRunResult,
    ToolExecutionRecord,
)
from payments_intelligence.agents.persistence import (
    InvestigationPersistenceRecord,
    build_persistence_record,
    parse_investigation_sections,
)

ROOT = Path(__file__).resolve().parents[2]

BUNDLE_RESOURCE = ROOT / "bundle/resources/fraud_investigation_agent.yml"

STORE_NOTEBOOK = ROOT / "notebooks/agents/12_create_agent_investigation_store.py"

PERSISTENCE_MODULE = ROOT / "src/payments_intelligence/agents/persistence.py"

RESPONSES_MODULE = ROOT / "src/payments_intelligence/agents/responses_agent.py"

RUNNER = ROOT / "scripts/agents/12_run_fraud_investigation_agent.py"

DEMO_RUNNER = ROOT / "scripts/agents/12_run_agent_demo_scenarios.py"


SAMPLE_FINAL_TEXT = """## Investigation Assessment
The available evidence warrants review, but it does not independently establish fraud. Human review is required.

## Risk Indicators
- Card-not-present transaction
- Cross-border activity

## Counter-Indicators
- Historical behavior provides some legitimate explanation

## Model Signal
Fraud probability is elevated. The model signal is not proof of fraud.

## Evidence Reviewed
- get_transaction_context
- get_fraud_evidence
- search_fraud_knowledge

## Knowledge Sources
- [SOURCE decision_standard_guide_chunk_001]

## Limitations
Customer confirmation and device intelligence were not available.

## Recommended Next Steps
- Review customer/device history
- Contact the customer through an approved channel if required
"""


def _read(
    path: Path,
) -> str:
    """Read one repository source file."""

    return path.read_text(encoding="utf-8")


def _load_yaml(
    path: Path,
) -> dict[str, Any]:
    """Read one YAML resource as a dictionary."""

    with path.open(encoding="utf-8") as file:
        content = yaml.safe_load(file)

    assert isinstance(
        content,
        dict,
    )

    return content


def _sample_result() -> AgentRunResult:
    """Return a stable sample agent result for persistence tests."""

    return AgentRunResult(
        transaction_id=("txn-00000001"),
        final_text=(SAMPLE_FINAL_TEXT),
        generation_model=("claude-sonnet-4-6"),
        trace_id=("tr-test-123"),
        tool_calls=(
            ToolExecutionRecord(
                tool_use_id=("toolu-1"),
                tool_name=("get_transaction_context"),
                arguments={"transaction_id": "txn-00000001"},
                result={
                    "tool_name": "get_transaction_context",
                    "ok": True,
                    "payload": {"transaction_id": "txn-00000001"},
                    "error": None,
                },
            ),
            ToolExecutionRecord(
                tool_use_id=("toolu-2"),
                tool_name=("get_fraud_evidence"),
                arguments={"transaction_id": "txn-00000001"},
                result={
                    "tool_name": "get_fraud_evidence",
                    "ok": True,
                    "payload": {"fraud_probability": 0.81},
                    "error": None,
                },
            ),
        ),
    )


def test_m12c_files_exist() -> None:
    for path in (
        BUNDLE_RESOURCE,
        STORE_NOTEBOOK,
        PERSISTENCE_MODULE,
        RESPONSES_MODULE,
        RUNNER,
        DEMO_RUNNER,
    ):
        assert path.exists(), str(path)


def test_bundle_creates_store_after_evidence() -> None:
    bundle = _load_yaml(BUNDLE_RESOURCE)

    job = bundle["resources"]["jobs"]["fraud_investigation_agent_setup"]

    tasks = {task["task_key"]: task for task in job["tasks"]}

    assert set(tasks) == {
        "build_agent_evidence",
        "create_agent_investigation_store",
    }

    assert tasks["create_agent_investigation_store"]["depends_on"] == [{"task_key": "build_agent_evidence"}]


def test_store_uses_governed_delta_features() -> None:
    source = _read(STORE_NOTEBOOK)

    assert "fraud_agent_investigations" in source

    assert "delta.enableChangeDataFeed" in source

    assert "delta.enableRowTracking" in source

    assert "PRIMARY KEY (investigation_id)" in source


def test_store_contains_trace_and_agent_metadata() -> None:
    source = _read(STORE_NOTEBOOK)

    for field in (
        "investigation_id",
        "transaction_id",
        "agent_version",
        "generation_provider",
        "generation_model",
        "tools_used",
        "tool_call_count",
        "trace_id",
        "duration_seconds",
        "created_at",
    ):
        assert field in source


def test_store_does_not_define_autonomous_fraud_decision() -> None:
    source = _read(STORE_NOTEBOOK)

    ddl_start = source.index("CREATE TABLE IF NOT EXISTS")

    ddl_end = source.index("FORBIDDEN_COLUMNS")

    ddl = source[ddl_start:ddl_end].lower()

    for forbidden in (
        "fraud_decision",
        "fraud_outcome",
        "is_confirmed_fraud",
        "block_card",
        "freeze_account",
        "decline_transaction",
    ):
        assert forbidden not in ddl


def test_store_has_explicit_forbidden_column_guard() -> None:
    source = _read(STORE_NOTEBOOK)

    assert "FORBIDDEN_COLUMNS" in source

    assert "leaked_columns" in source

    for forbidden in (
        "fraud_decision",
        "fraud_outcome",
        "is_confirmed_fraud",
        "block_card",
        "freeze_account",
        "decline_transaction",
    ):
        assert forbidden in source


def test_final_response_parser_extracts_sections() -> None:
    sections = parse_investigation_sections(SAMPLE_FINAL_TEXT)

    assert "warrants review" in sections.assessment

    assert sections.risk_indicators == (
        "Card-not-present transaction",
        "Cross-border activity",
    )

    assert sections.counter_indicators == ("Historical behavior provides some legitimate explanation",)

    assert "not proof of fraud" in sections.model_signal

    assert sections.evidence_reviewed == (
        "get_transaction_context",
        "get_fraud_evidence",
        "search_fraud_knowledge",
    )

    assert sections.knowledge_sources == ("[SOURCE decision_standard_guide_chunk_001]",)

    assert len(sections.recommended_next_steps) == 2


def test_build_persistence_record_preserves_trace_and_tools() -> None:
    record = build_persistence_record(
        result=(_sample_result()),
        duration_seconds=2.5,
    )

    assert isinstance(
        record,
        InvestigationPersistenceRecord,
    )

    assert record.transaction_id == "txn-00000001"

    assert record.trace_id == "tr-test-123"

    assert record.generation_provider == "anthropic"

    assert record.generation_model == "claude-sonnet-4-6"

    assert record.tools_used == (
        "get_transaction_context",
        "get_fraud_evidence",
    )

    assert record.tool_call_count == 2

    assert record.duration_seconds == 2.5

    assert record.investigation_id


def test_persistence_record_has_unique_investigation_ids() -> None:
    first = build_persistence_record(
        result=(_sample_result()),
        duration_seconds=1.0,
    )

    second = build_persistence_record(
        result=(_sample_result()),
        duration_seconds=1.0,
    )

    assert first.investigation_id != second.investigation_id


def test_persistence_record_does_not_include_ground_truth_or_decision_fields() -> None:
    record = build_persistence_record(
        result=(_sample_result()),
        duration_seconds=1.0,
    )

    fields = set(record.to_dict())

    for forbidden in (
        "fraud_decision",
        "fraud_outcome",
        "is_confirmed_fraud",
        "block_card",
        "freeze_account",
        "decline_transaction",
    ):
        assert forbidden not in fields


def test_persistence_preserves_final_response() -> None:
    record = build_persistence_record(
        result=(_sample_result()),
        duration_seconds=1.0,
    )

    assert record.final_response == SAMPLE_FINAL_TEXT

    assert "Human review is required" in record.final_response


def test_persistence_serializes_tool_trajectory() -> None:
    record = build_persistence_record(
        result=(_sample_result()),
        duration_seconds=1.0,
    )

    assert "get_transaction_context" in record.tool_execution_json

    assert "get_fraud_evidence" in record.tool_execution_json

    assert "toolu-1" in record.tool_execution_json


def test_persistence_is_append_only_insert() -> None:
    source = _read(PERSISTENCE_MODULE)

    normalized = " ".join(source.upper().split())

    assert "INSERT INTO" in normalized

    assert "UPDATE " not in normalized

    assert "DELETE FROM" not in normalized

    assert "MERGE INTO" not in normalized


def test_persistence_stores_delta_array_fields() -> None:
    source = _read(PERSISTENCE_MODULE)

    assert "ARRAY<STRING>" in source

    for field in (
        "tools_used",
        "risk_indicators",
        "counter_indicators",
        "evidence_reviewed",
        "knowledge_sources",
        "recommended_next_steps",
    ):
        assert field in source


def test_runner_supports_no_persist() -> None:
    source = _read(RUNNER)

    assert "--no-persist" in source

    assert "args.no_persist" in source

    assert "DatabricksInvestigationPersistence" in source

    assert "build_persistence_record" in source

    assert "persistence.persist" in source


def test_local_runner_tracks_to_databricks_and_supports_responses_interface() -> None:
    source = _read(RUNNER)

    # Avoid exact formatting assertions such as:
    #
    # default="/Shared/..."
    #
    # Ruff is free to wrap argparse values.
    assert "mlflow.set_tracking_uri" in source

    assert "databricks://" in source

    assert "args.profile" in source

    assert "/Shared/epip-dev-fraud-agent" in source

    assert "--interface" in source

    assert '"core"' in source

    assert '"responses"' in source

    assert "FraudInvestigationResponsesAgent" in source


def test_runner_emits_m12c_ready_marker() -> None:
    source = _read(RUNNER)

    assert "EPIP_M12C_FRAUD_AGENT_READY" in source


def test_responses_agent_exposes_tool_calls_for_persistence() -> None:
    source = _read(RESPONSES_MODULE)

    assert "custom_outputs" in source

    assert '"tool_calls"' in source

    assert "result.tool_calls" in source

    assert "record.to_dict()" in source

    assert '"trace_id"' in source


def test_demo_has_four_portfolio_scenarios() -> None:
    source = _read(DEMO_RUNNER)

    for selector in (
        "select_strong_risk_scenario",
        "select_cross_border_counterexample",
        "select_duplicate_delivery_scenario",
        "select_insufficient_evidence_scenario",
    ):
        assert selector in source

    assert "EPIP_M12C_DEMO_SCENARIOS_COMPLETE" in source


def test_duplicate_demo_uses_real_bronze_delivery_metadata() -> None:
    source = _read(DEMO_RUNNER)

    assert ".bronze.payment_events" in source

    assert "event_id" in source

    assert "transaction_id" in source

    assert "physical_deliveries" in source

    assert "delivery_scenario" in source

    assert "kafka_offsets" in source

    assert "COUNT(*) > 1" in source


def test_demo_scenarios_use_agent_evidence() -> None:
    source = _read(DEMO_RUNNER)

    assert "agent_fraud_evidence" in source or "fraud_evidence_view" in source

    assert "fraud_probability" in source

    assert "is_cross_border" in source


def test_demo_runner_persists_successful_investigations() -> None:
    source = _read(DEMO_RUNNER)

    assert "DatabricksInvestigationPersistence" in source

    assert "build_persistence_record" in source

    assert "persist" in source
