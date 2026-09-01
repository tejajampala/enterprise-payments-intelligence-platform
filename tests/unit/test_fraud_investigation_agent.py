from pathlib import Path
from typing import Any

import yaml

from payments_intelligence.agents.config import (
    AgentSettings,
    validate_transaction_id,
)
from payments_intelligence.agents.tools import (
    APPROVED_TOOL_NAMES,
    GET_FRAUD_EVIDENCE,
    GET_TRANSACTION_CONTEXT,
    SEARCH_FRAUD_KNOWLEDGE,
    FraudInvestigationTools,
)

ROOT = Path(__file__).resolve().parents[2]

BUNDLE_RESOURCE = ROOT / "bundle/resources/fraud_investigation_agent.yml"

EVIDENCE_NOTEBOOK = ROOT / "notebooks/agents/12_build_agent_evidence.py"

INVESTIGATION_STORE_NOTEBOOK = ROOT / "notebooks/agents/12_create_agent_investigation_store.py"

CONFIG_MODULE = ROOT / "src/payments_intelligence/agents/config.py"

CONTRACTS_MODULE = ROOT / "src/payments_intelligence/agents/contracts.py"

DATA_ACCESS_MODULE = ROOT / "src/payments_intelligence/agents/data_access.py"

TOOLS_MODULE = ROOT / "src/payments_intelligence/agents/tools.py"

TOOL_SMOKE_SCRIPT = ROOT / "scripts/agents/12_test_agent_tools.py"


def _read(
    path: Path,
) -> str:
    return path.read_text(encoding="utf-8")


def _without_whitespace(
    value: str,
) -> str:
    """Return source text without formatting whitespace."""

    return "".join(value.split())


def _load_yaml(
    path: Path,
) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        content = yaml.safe_load(file)

    assert isinstance(
        content,
        dict,
    )

    return content


class FakeDataAccess:
    """Small fake implementation used to unit test the tool dispatcher."""

    def get_transaction_context(
        self,
        transaction_id: str,
    ) -> dict[str, Any] | None:
        return {
            "transaction_id": transaction_id,
            "amount": 125.0,
            "transaction_country": "AU",
        }

    def get_fraud_evidence(
        self,
        transaction_id: str,
    ) -> dict[str, Any] | None:
        return {
            "transaction_id": transaction_id,
            "fraud_probability": 0.42,
            "predicted_fraud": 0,
        }

    def search_fraud_knowledge(
        self,
        question: str,
    ) -> list[dict[str, Any]]:
        return [
            {
                "rank": 1,
                "chunk_id": ("decision_standard_guide_chunk_001"),
                "doc_id": ("decision_standard_guide"),
                "title": ("Decision Standard"),
                "category": ("decision"),
                "chunk_text": question,
            }
        ]


def test_m12_files_exist() -> None:
    for path in (
        BUNDLE_RESOURCE,
        EVIDENCE_NOTEBOOK,
        INVESTIGATION_STORE_NOTEBOOK,
        CONFIG_MODULE,
        CONTRACTS_MODULE,
        DATA_ACCESS_MODULE,
        TOOLS_MODULE,
        TOOL_SMOKE_SCRIPT,
    ):
        assert path.exists(), str(path)


def test_bundle_has_serverless_agent_setup_tasks() -> None:
    bundle = _load_yaml(BUNDLE_RESOURCE)

    job = bundle["resources"]["jobs"]["fraud_investigation_agent_setup"]

    # M12 remains serverless.
    assert "job_clusters" not in job

    tasks = job["tasks"]

    # M12A creates the evidence layer.
    # M12C adds the governed investigation-history store.
    assert len(tasks) == 2

    task_keys = [task["task_key"] for task in tasks]

    assert task_keys == [
        "build_agent_evidence",
        "create_agent_investigation_store",
    ]

    assert tasks[0]["environment_key"] == "agent_setup_env"

    assert tasks[1]["environment_key"] == "agent_setup_env"

    assert tasks[1]["depends_on"] == [{"task_key": "build_agent_evidence"}]


def test_evidence_notebook_creates_expected_views_and_functions() -> None:
    source = _read(EVIDENCE_NOTEBOOK)

    for name in (
        "agent_transaction_context",
        "agent_fraud_evidence",
        "get_transaction_context",
        "get_fraud_evidence",
    ):
        assert name in source

    assert "RETURNS TABLE" in source

    assert "READS SQL DATA" in source


def test_evidence_layer_has_runtime_leakage_guard() -> None:
    source = _read(EVIDENCE_NOTEBOOK)

    assert "FORBIDDEN_AGENT_COLUMNS" in source

    assert '"fraud_outcome"' in source

    assert '"is_confirmed_fraud"' in source

    assert "leaked_columns" in source


def test_evidence_view_uses_point_in_time_feature_keys() -> None:
    source = _without_whitespace(_read(EVIDENCE_NOTEBOOK))

    assert "transaction_features.transaction_event_timestamp=customer_features.feature_timestamp" in source

    assert "transaction_features.transaction_event_timestamp=merchant_features.feature_timestamp" in source


def test_evidence_uses_actual_m10_prediction_contract() -> None:
    source = _read(EVIDENCE_NOTEBOOK)

    assert "fraud_probability" in source

    assert "predicted_fraud" in source

    assert "fraud_batch_predictions" in source


def test_transaction_id_validation() -> None:
    assert validate_transaction_id("txn-00000001") == "txn-00000001"


def test_transaction_id_rejects_noncanonical_value() -> None:
    try:
        validate_transaction_id("txn-1 OR 1=1")

    except ValueError:
        pass

    else:
        raise AssertionError("Invalid transaction ID should be rejected")


def test_settings_bind_existing_m11_index() -> None:
    settings = AgentSettings()

    assert settings.knowledge_index_name == "payments_dev.ai.fraud_investigation_knowledge_index"

    assert settings.search_endpoint_name == "epip-dev-fraud-knowledge-search"

    assert settings.search_top_k == 3

    assert settings.max_tool_calls == 6


def test_only_three_tools_are_exposed() -> None:
    assert APPROVED_TOOL_NAMES == {
        GET_TRANSACTION_CONTEXT,
        GET_FRAUD_EVIDENCE,
        SEARCH_FRAUD_KNOWLEDGE,
    }


def test_no_action_or_write_tools_are_exposed() -> None:
    forbidden_tokens = {
        "block",
        "decline",
        "delete",
        "freeze",
        "insert",
        "update",
    }

    for tool_name in APPROVED_TOOL_NAMES:
        assert not any(token in tool_name.lower() for token in forbidden_tokens)


def test_anthropic_tool_schemas_reject_extra_properties() -> None:
    schemas = FraudInvestigationTools.anthropic_tool_schemas()

    assert len(schemas) == 3

    for schema in schemas:
        assert schema["input_schema"]["additionalProperties"] is False

        assert schema["input_schema"]["required"]


def test_tool_dispatch_returns_transaction_context() -> None:
    tools = FraudInvestigationTools(FakeDataAccess())

    result = tools.dispatch(
        GET_TRANSACTION_CONTEXT,
        {"transaction_id": "txn-00000001"},
    )

    assert result.ok is True

    assert isinstance(
        result.payload,
        dict,
    )

    assert result.payload["transaction_id"] == "txn-00000001"


def test_tool_dispatch_returns_fraud_evidence() -> None:
    tools = FraudInvestigationTools(FakeDataAccess())

    result = tools.dispatch(
        GET_FRAUD_EVIDENCE,
        {"transaction_id": "txn-00000001"},
    )

    assert result.ok is True

    assert isinstance(
        result.payload,
        dict,
    )

    assert result.payload["fraud_probability"] == 0.42


def test_tool_dispatch_returns_knowledge() -> None:
    tools = FraudInvestigationTools(FakeDataAccess())

    result = tools.dispatch(
        SEARCH_FRAUD_KNOWLEDGE,
        {"question": ("How should duplicate payment delivery be investigated?")},
    )

    assert result.ok is True

    assert isinstance(
        result.payload,
        list,
    )

    assert result.payload[0]["rank"] == 1


def test_unknown_tool_is_rejected() -> None:
    tools = FraudInvestigationTools(FakeDataAccess())

    result = tools.dispatch(
        "freeze_account",
        {"transaction_id": "txn-00000001"},
    )

    assert result.ok is False

    assert result.error == "UNKNOWN_TOOL: freeze_account"


def test_extra_tool_arguments_are_rejected() -> None:
    tools = FraudInvestigationTools(FakeDataAccess())

    result = tools.dispatch(
        GET_TRANSACTION_CONTEXT,
        {
            "transaction_id": "txn-00000001",
            "sql": "SELECT * FROM anything",
        },
    )

    assert result.ok is False

    assert result.error is not None

    assert "Expected exactly one tool argument" in result.error


def test_data_access_enforces_read_only_queries() -> None:
    source = _read(DATA_ACCESS_MODULE)

    # Trusted EPIP application code may execute:
    #
    # SELECT ...
    #
    # WITH ... SELECT ...
    #
    # This is required by the M12C demo-scenario selectors.
    assert '"SELECT "' in source

    assert '"WITH "' in source

    assert "read-only SELECT statements" in source

    # The internal SQL helper must explicitly reject
    # data mutation, DDL, and permission-changing SQL.
    for forbidden_operation in (
        "DELETE",
        "INSERT",
        "MERGE",
        "UPDATE",
        "TRUNCATE",
        "DROP",
        "ALTER",
        "CREATE",
        "REPLACE",
        "GRANT",
        "REVOKE",
    ):
        assert forbidden_operation in source

    # The SQL boundary is implemented with an explicit
    # forbidden-operation regex.
    assert "forbidden_pattern" in source

    assert "detected_forbidden" in source


def test_ai_search_is_bounded_hybrid_top_k() -> None:
    source = _read(DATA_ACCESS_MODULE)

    config_source = _read(CONFIG_MODULE)

    # AI Search remains HYBRID.
    assert 'query_type="HYBRID"' in source

    # Retrieval count comes from centralized configuration.
    assert "num_results=" in source

    assert "self.settings.search_top_k" in source

    # Default retrieval is bounded to Top-3.
    assert "search_top_k: int = 3" in config_source

    # Configuration prevents a caller from increasing it
    # above the intended M12 limit.
    assert "self.search_top_k > 3" in config_source


def test_investigation_store_notebook_is_part_of_m12() -> None:
    source = _read(INVESTIGATION_STORE_NOTEBOOK)

    assert "fraud_agent_investigations" in source

    assert "investigation_id" in source

    assert "trace_id" in source

    assert "delta.enableChangeDataFeed" in source

    assert "delta.enableRowTracking" in source


def test_investigation_store_does_not_define_autonomous_decision_columns() -> None:
    source = _read(INVESTIGATION_STORE_NOTEBOOK)

    # These values may appear in the notebook's forbidden-column
    # validation set, so we validate that they are not declared
    # as SQL table columns.
    forbidden_definitions = (
        "fraud_decision STRING",
        "fraud_outcome STRING",
        "is_confirmed_fraud BOOLEAN",
        "block_card STRING",
        "freeze_account STRING",
        "decline_transaction STRING",
    )

    for forbidden_definition in forbidden_definitions:
        assert forbidden_definition not in source


def test_tool_smoke_script_tests_all_three_tools() -> None:
    source = _read(TOOL_SMOKE_SCRIPT)

    assert "GET_TRANSACTION_CONTEXT" in source

    assert "GET_FRAUD_EVIDENCE" in source

    assert "SEARCH_FRAUD_KNOWLEDGE" in source

    assert "EPIP_M12A_AGENT_TOOLS_READY" in source
