"""Milestone 12A live smoke test for the three approved investigation tools."""

from __future__ import annotations

import argparse
import json
from typing import Any

from payments_intelligence.agents.config import (
    AgentSettings,
)
from payments_intelligence.agents.data_access import (
    DatabricksAgentDataAccess,
)
from payments_intelligence.agents.tools import (
    GET_FRAUD_EVIDENCE,
    GET_TRANSACTION_CONTEXT,
    SEARCH_FRAUD_KNOWLEDGE,
    FraudInvestigationTools,
)

DEFAULT_KNOWLEDGE_QUERY = (
    "How should an investigator assess a "
    "payment with unusual geography, "
    "card-not-present activity, velocity "
    "signals, or duplicate event delivery?"
)


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=("Smoke test EPIP M12A governed fraud-investigation tools."),
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
        "--knowledge-query",
        default=DEFAULT_KNOWLEDGE_QUERY,
    )

    return parser.parse_args()


def print_result(
    title: str,
    value: dict[str, Any],
) -> None:

    print()

    print("=" * 80)

    print(title)

    print("=" * 80)

    print(
        json.dumps(
            value,
            indent=2,
            default=str,
        )
    )


def require_success(
    result: dict[str, Any],
) -> None:

    if not bool(result.get("ok")):
        raise RuntimeError(f"Tool smoke test failed for {result.get('tool_name')}: {result.get('error')}")


def main() -> None:

    args = parse_args()

    settings = AgentSettings(
        profile=args.profile,
        catalog=args.catalog,
        search_endpoint_name=(args.search_endpoint_name),
    )

    data_access = DatabricksAgentDataAccess(
        settings=settings,
        warehouse_id=(args.warehouse_id),
    )

    transaction_id = args.transaction_id or data_access.find_sample_transaction_id()

    tools = FraudInvestigationTools(data_access)

    print(
        "Databricks profile:",
        settings.profile,
    )

    print(
        "Catalog:",
        settings.catalog,
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
        "Transaction ID:",
        transaction_id,
    )

    transaction_context = tools.dispatch(
        GET_TRANSACTION_CONTEXT,
        {"transaction_id": (transaction_id)},
    ).to_dict()

    require_success(transaction_context)

    print_result(
        "1. GET TRANSACTION CONTEXT",
        transaction_context,
    )

    fraud_evidence = tools.dispatch(
        GET_FRAUD_EVIDENCE,
        {"transaction_id": (transaction_id)},
    ).to_dict()

    require_success(fraud_evidence)

    print_result(
        "2. GET FRAUD EVIDENCE",
        fraud_evidence,
    )

    knowledge = tools.dispatch(
        SEARCH_FRAUD_KNOWLEDGE,
        {"question": (args.knowledge_query)},
    ).to_dict()

    require_success(knowledge)

    print_result(
        "3. SEARCH FRAUD KNOWLEDGE",
        knowledge,
    )

    print()

    print("EPIP_M12A_AGENT_TOOLS_READY")


if __name__ == "__main__":
    main()
