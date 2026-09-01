"""Run and optionally persist the EPIP Milestone 12 fraud-investigation agent."""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any

import mlflow

from payments_intelligence.agents.config import (
    AgentSettings,
    validate_transaction_id,
)
from payments_intelligence.agents.contracts import (
    AgentRunResult,
    ToolExecutionRecord,
)
from payments_intelligence.agents.data_access import (
    DatabricksAgentDataAccess,
)
from payments_intelligence.agents.fraud_investigation_agent import (
    FraudInvestigationAgentCore,
)
from payments_intelligence.agents.persistence import (
    DatabricksInvestigationPersistence,
    build_persistence_record,
)
from payments_intelligence.agents.responses_agent import (
    FraudInvestigationResponsesAgent,
)
from payments_intelligence.agents.tools import (
    FraudInvestigationTools,
)

DEFAULT_QUESTION = (
    "Investigate this payment for fraud risk. "
    "Review transaction context, behavioral and model "
    "signals, and fraud-investigation knowledge when "
    "they materially help."
)


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=("Run the EPIP M12 Claude fraud-investigation agent locally."),
    )

    parser.add_argument(
        "--profile",
        default="PAYMENTS_DEV",
    )

    parser.add_argument(
        "--catalog",
        default="payments_dev",
    )

    parser.add_argument(
        "--warehouse-id",
        default=None,
    )

    parser.add_argument(
        "--transaction-id",
        default=None,
    )

    parser.add_argument(
        "--search-endpoint-name",
        default=("epip-dev-fraud-knowledge-search"),
    )

    parser.add_argument(
        "--generation-model",
        default="claude-sonnet-4-6",
    )

    parser.add_argument(
        "--experiment-name",
        default=("/Shared/epip-dev-fraud-agent"),
    )

    parser.add_argument(
        "--question",
        default=DEFAULT_QUESTION,
    )

    parser.add_argument(
        "--interface",
        choices=(
            "core",
            "responses",
        ),
        default="responses",
    )

    parser.add_argument(
        "--no-persist",
        action="store_true",
        help=("Run without writing to fraud_agent_investigations."),
    )

    return parser.parse_args()


def require_environment_variable(
    name: str,
) -> str:

    value = os.environ.get(name)

    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")

    return value


def extract_responses_text(
    response_payload: dict[str, Any],
) -> str:

    text_parts: list[str] = []

    for item in response_payload.get(
        "output",
        [],
    ):
        if item.get("type") != "message":
            continue

        for content in item.get(
            "content",
            [],
        ):
            if content.get("type") == "output_text":
                text = str(content.get("text") or "").strip()

                if text:
                    text_parts.append(text)

    return "\n".join(text_parts)


def agent_result_from_responses(
    response_payload: dict[str, Any],
    final_text: str,
) -> AgentRunResult:

    custom_outputs = response_payload.get("custom_outputs") or {}

    raw_tool_calls = custom_outputs.get("tool_calls") or []

    tool_calls = tuple(
        ToolExecutionRecord(
            tool_use_id=str(item.get("tool_use_id") or ""),
            tool_name=str(item.get("tool_name") or ""),
            arguments=dict(item.get("arguments") or {}),
            result=dict(item.get("result") or {}),
            repeated_call=bool(
                item.get(
                    "repeated_call",
                    False,
                )
            ),
            scope_violation=bool(
                item.get(
                    "scope_violation",
                    False,
                )
            ),
        )
        for item in raw_tool_calls
    )

    return AgentRunResult(
        transaction_id=(validate_transaction_id(str(custom_outputs["transaction_id"]))),
        final_text=final_text,
        generation_model=str(custom_outputs["generation_model"]),
        trace_id=(str(custom_outputs["trace_id"]) if custom_outputs.get("trace_id") else None),
        tool_calls=tool_calls,
    )


def main() -> None:

    args = parse_args()

    require_environment_variable("ANTHROPIC_API_KEY")

    os.environ["DATABRICKS_CONFIG_PROFILE"] = args.profile

    mlflow.set_tracking_uri(f"databricks://{args.profile}")

    mlflow.set_experiment(args.experiment_name)

    settings = AgentSettings(
        profile=args.profile,
        catalog=args.catalog,
        search_endpoint_name=(args.search_endpoint_name),
    )

    data_access = DatabricksAgentDataAccess(
        settings=settings,
        warehouse_id=(args.warehouse_id),
    )

    transaction_id = (
        validate_transaction_id(args.transaction_id)
        if args.transaction_id
        else data_access.find_sample_transaction_id()
    )

    tools = FraudInvestigationTools(data_access=data_access)

    core = FraudInvestigationAgentCore(
        settings=settings,
        tools=tools,
        generation_model=(args.generation_model),
    )

    print(
        "MLflow tracking URI:",
        mlflow.get_tracking_uri(),
    )

    print(
        "MLflow experiment:",
        args.experiment_name,
    )

    print(
        "Databricks profile:",
        settings.profile,
    )

    print(
        "SQL warehouse ID:",
        data_access.warehouse_id,
    )

    print(
        "AI Search endpoint:",
        settings.search_endpoint_name,
    )

    print(
        "AI Search index:",
        settings.knowledge_index_name,
    )

    print(
        "Generation model:",
        args.generation_model,
    )

    print(
        "Interface:",
        args.interface,
    )

    print(
        "Transaction ID:",
        transaction_id,
    )

    print(
        "Persistence enabled:",
        not args.no_persist,
    )

    started = time.monotonic()

    if args.interface == "responses":
        agent = FraudInvestigationResponsesAgent(core=core)

        response = agent.predict(
            {
                "input": [
                    {
                        "role": "user",
                        "content": (f"{args.question}\n\nTransaction: {transaction_id}"),
                    }
                ],
                "custom_inputs": {
                    "transaction_id": transaction_id,
                },
            }
        )

        response_payload = response.model_dump(exclude_none=True)

        final_text = extract_responses_text(response_payload)

        result = agent_result_from_responses(
            response_payload=(response_payload),
            final_text=final_text,
        )

        print("\n" + "=" * 80)

        print("RESPONSES AGENT METADATA")

        print("=" * 80)

        print(
            json.dumps(
                response_payload.get("custom_outputs") or {},
                indent=2,
                default=str,
            )
        )

    else:
        result = core.run_investigation_traced(
            transaction_id=(transaction_id),
            investigator_question=(args.question),
        )

        final_text = result.final_text

        print("\n" + "=" * 80)

        print("AGENT EXECUTION METADATA")

        print("=" * 80)

        print(
            json.dumps(
                result.to_dict(),
                indent=2,
                default=str,
            )
        )

    duration_seconds = time.monotonic() - started

    flush_traces = getattr(
        mlflow,
        "flush_trace_async_logging",
        None,
    )

    if callable(flush_traces):
        flush_traces()

    investigation_id: str | None = None

    if not args.no_persist:
        persistence = DatabricksInvestigationPersistence(
            settings=settings,
            warehouse_id=(data_access.warehouse_id),
        )

        record = build_persistence_record(
            result=result,
            duration_seconds=(duration_seconds),
        )

        investigation_id = persistence.persist(record)

    print("\n" + "=" * 80)

    print("FRAUD INVESTIGATION ASSESSMENT")

    print("=" * 80)

    print(final_text)

    print("\n" + "=" * 80)

    print("PERSISTENCE")

    print("=" * 80)

    print(
        "Investigation ID:",
        investigation_id or "NOT_PERSISTED",
    )

    print(
        "Trace ID:",
        result.trace_id or "NOT_AVAILABLE",
    )

    print(
        "Duration seconds:",
        round(
            duration_seconds,
            3,
        ),
    )

    print(
        "Persisted:",
        not args.no_persist,
    )

    print("\nEPIP_M12C_FRAUD_AGENT_READY")


if __name__ == "__main__":
    main()
