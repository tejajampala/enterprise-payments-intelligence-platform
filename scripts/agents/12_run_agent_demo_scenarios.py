"""Run four reproducible EPIP Milestone 12 fraud-agent portfolio scenarios."""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from typing import Any

import mlflow

from payments_intelligence.agents.config import AgentSettings, validate_transaction_id
from payments_intelligence.agents.data_access import DatabricksAgentDataAccess
from payments_intelligence.agents.fraud_investigation_agent import FraudInvestigationAgentCore
from payments_intelligence.agents.persistence import (
    DatabricksInvestigationPersistence,
    build_persistence_record,
)
from payments_intelligence.agents.tools import FraudInvestigationTools


@dataclass(frozen=True, slots=True)
class DemoScenario:
    name: str
    transaction_id: str
    question: str
    selection_evidence: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run four reproducible EPIP fraud-investigation agent demo scenarios.",
    )
    parser.add_argument("--profile", default="PAYMENTS_DEV")
    parser.add_argument("--catalog", default="payments_dev")
    parser.add_argument("--warehouse-id", default=None)
    parser.add_argument(
        "--search-endpoint-name",
        default="epip-dev-fraud-knowledge-search",
    )
    parser.add_argument("--generation-model", default="claude-sonnet-4-6")
    parser.add_argument("--experiment-name", default="/Shared/epip-dev-fraud-agent")
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Run the four scenarios without writing investigation history rows.",
    )
    return parser.parse_args()


def require_environment_variable(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def query_rows(
    data_access: DatabricksAgentDataAccess,
    statement: str,
    parameters: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Use the existing read-only adapter for demo-case selection queries."""

    return data_access._query_rows(statement, parameters)  # noqa: SLF001


def select_strong_risk_scenario(
    data_access: DatabricksAgentDataAccess,
    settings: AgentSettings,
) -> DemoScenario:
    rows = query_rows(
        data_access,
        f"""
        SELECT
            transaction_id,
            fraud_probability,
            predicted_fraud,
            is_cross_border,
            is_card_not_present,
            customer_txn_count_1d,
            customer_foreign_rate_30d,
            merchant_decline_rate_30d
        FROM {settings.fraud_evidence_view}
        WHERE fraud_probability IS NOT NULL
        ORDER BY
            CASE WHEN is_cross_border AND is_card_not_present THEN 0 ELSE 1 END,
            fraud_probability DESC,
            customer_txn_count_1d DESC
        LIMIT 1
        """,
    )

    if not rows:
        raise RuntimeError("Unable to select a strong-risk demo transaction")

    row = rows[0]
    transaction_id = validate_transaction_id(str(row["transaction_id"]))

    return DemoScenario(
        name="Strong fraud indicators",
        transaction_id=transaction_id,
        question=(
            "Investigate this transaction for fraud risk. Pay particular attention to unusual geography, "
            "card-present/card-not-present behavior, short-term velocity, merchant behavior, and the Champion "
            "fraud-model signal. Use fraud-investigation knowledge when it helps interpret the evidence."
        ),
        selection_evidence=row,
    )


def select_cross_border_counterexample(
    data_access: DatabricksAgentDataAccess,
    settings: AgentSettings,
) -> DemoScenario:
    rows = query_rows(
        data_access,
        f"""
        SELECT
            transaction_id,
            fraud_probability,
            predicted_fraud,
            is_cross_border,
            is_card_not_present,
            customer_txn_count_30d,
            customer_foreign_rate_30d,
            merchant_foreign_rate_30d
        FROM {settings.fraud_evidence_view}
        WHERE is_cross_border = true
          AND fraud_probability IS NOT NULL
        ORDER BY
            fraud_probability ASC,
            customer_foreign_rate_30d DESC,
            customer_txn_count_30d DESC
        LIMIT 1
        """,
    )

    if not rows:
        raise RuntimeError("Unable to select a cross-border counterexample transaction")

    row = rows[0]
    transaction_id = validate_transaction_id(str(row["transaction_id"]))

    return DemoScenario(
        name="Cross-border counterexample",
        transaction_id=transaction_id,
        question=(
            "Investigate this cross-border transaction carefully. Do not treat cross-border activity by itself "
            "as proof of fraud. Identify both risk indicators and counter-indicators from historical behavior, "
            "merchant context, and the fraud-model signal."
        ),
        selection_evidence=row,
    )


def select_duplicate_delivery_scenario(
    data_access: DatabricksAgentDataAccess,
    settings: AgentSettings,
) -> DemoScenario:
    rows = query_rows(
        data_access,
        f"""
        WITH duplicate_events AS (
            SELECT
                event_id,
                transaction_id,
                COUNT(*) AS physical_deliveries,
                array_sort(collect_set(delivery_scenario)) AS delivery_scenarios,
                array_sort(collect_set(kafka_offset)) AS kafka_offsets
            FROM {settings.catalog}.bronze.payment_events
            WHERE event_id IS NOT NULL
              AND transaction_id IS NOT NULL
            GROUP BY event_id, transaction_id
            HAVING COUNT(*) > 1
        )
        SELECT
            duplicate_events.event_id,
            duplicate_events.transaction_id,
            duplicate_events.physical_deliveries,
            duplicate_events.delivery_scenarios,
            duplicate_events.kafka_offsets
        FROM duplicate_events
        INNER JOIN {settings.transaction_context_view} AS context
            ON duplicate_events.transaction_id = context.transaction_id
        ORDER BY duplicate_events.physical_deliveries DESC
        LIMIT 1
        """,
    )

    if not rows:
        raise RuntimeError(
            "No duplicate physical Kafka delivery is available in the Bronze streaming data. "
            "Run the M4 duplicate-delivery demo data before this M12 scenario."
        )

    row = rows[0]
    transaction_id = validate_transaction_id(str(row["transaction_id"]))

    observation = json.dumps(
        {
            "event_id": row.get("event_id"),
            "physical_deliveries": row.get("physical_deliveries"),
            "delivery_scenarios": row.get("delivery_scenarios"),
            "kafka_offsets": row.get("kafka_offsets"),
        },
        default=str,
    )

    return DemoScenario(
        name="Duplicate Kafka delivery semantics",
        transaction_id=transaction_id,
        question=(
            "Investigate this transaction. Streaming telemetry shows repeated physical Kafka deliveries for the "
            f"same business event: {observation}. Determine whether this observation proves multiple customer "
            "payments or can represent duplicate event delivery. Use the governed fraud knowledge when useful, "
            "and keep infrastructure delivery semantics separate from business-transaction semantics."
        ),
        selection_evidence=row,
    )


def select_insufficient_evidence_scenario(
    data_access: DatabricksAgentDataAccess,
    settings: AgentSettings,
) -> DemoScenario:
    rows = query_rows(
        data_access,
        f"""
        SELECT
            transaction_id,
            fraud_probability,
            predicted_fraud,
            is_cross_border,
            is_card_not_present,
            customer_txn_count_1d,
            customer_decline_rate_30d,
            merchant_decline_rate_30d
        FROM {settings.fraud_evidence_view}
        WHERE fraud_probability IS NOT NULL
        ORDER BY
            ABS(fraud_probability - 0.5) ASC,
            customer_txn_count_1d ASC
        LIMIT 1
        """,
    )

    if not rows:
        raise RuntimeError("Unable to select an insufficient-evidence demo transaction")

    row = rows[0]
    transaction_id = validate_transaction_id(str(row["transaction_id"]))

    return DemoScenario(
        name="Insufficient evidence",
        transaction_id=transaction_id,
        question=(
            "Investigate this transaction conservatively. If the available transaction, behavioral, model, and "
            "knowledge evidence is not sufficient for a strong assessment, say so explicitly and identify what "
            "additional human investigation would be useful rather than guessing."
        ),
        selection_evidence=row,
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
        search_endpoint_name=args.search_endpoint_name,
    )
    data_access = DatabricksAgentDataAccess(
        settings=settings,
        warehouse_id=args.warehouse_id,
    )
    tools = FraudInvestigationTools(data_access=data_access)
    core = FraudInvestigationAgentCore(
        settings=settings,
        tools=tools,
        generation_model=args.generation_model,
    )

    persistence = (
        None
        if args.no_persist
        else DatabricksInvestigationPersistence(
            settings=settings,
            warehouse_id=data_access.warehouse_id,
        )
    )

    scenarios = (
        select_strong_risk_scenario(data_access, settings),
        select_cross_border_counterexample(data_access, settings),
        select_duplicate_delivery_scenario(data_access, settings),
        select_insufficient_evidence_scenario(data_access, settings),
    )

    for index, scenario in enumerate(scenarios, start=1):
        print("\n" + "=" * 100)
        print(f"SCENARIO {index} — {scenario.name.upper()}")
        print("=" * 100)
        print("Transaction ID:", scenario.transaction_id)
        print("Selection evidence:")
        print(json.dumps(scenario.selection_evidence, indent=2, default=str))

        started = time.monotonic()
        result = core.run_investigation_traced(
            transaction_id=scenario.transaction_id,
            investigator_question=scenario.question,
        )
        duration_seconds = time.monotonic() - started

        investigation_id: str | None = None

        if persistence is not None:
            record = build_persistence_record(
                result=result,
                duration_seconds=duration_seconds,
            )
            investigation_id = persistence.persist(record)

        print("\nInvestigation ID:", investigation_id or "NOT_PERSISTED")
        print("Trace ID:", result.trace_id or "NOT_AVAILABLE")
        print("Tools used:", result.tools_used)
        print("Tool calls:", result.tool_call_count)
        print("Duration seconds:", round(duration_seconds, 3))
        print("\nAssessment:\n")
        print(result.final_text)

    flush_traces = getattr(mlflow, "flush_trace_async_logging", None)
    if callable(flush_traces):
        flush_traces()

    print("\nEPIP_M12C_DEMO_SCENARIOS_COMPLETE")


if __name__ == "__main__":
    main()
