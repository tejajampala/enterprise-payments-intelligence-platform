"""Run EPIP Milestone 13 fraud-agent evaluation and regression gates."""

from __future__ import annotations

import argparse
import json
import os
import time
from uuid import uuid4

import mlflow
from openai import OpenAI

from payments_intelligence.agents.config import AgentSettings
from payments_intelligence.agents.data_access import DatabricksAgentDataAccess
from payments_intelligence.agents.fraud_investigation_agent import (
    FraudInvestigationAgentCore,
)
from payments_intelligence.agents.tools import FraudInvestigationTools
from payments_intelligence.evaluation.contracts import AgentEvaluationResult
from payments_intelligence.evaluation.deterministic_scorers import (
    score_deterministic,
)
from payments_intelligence.evaluation.gates import (
    RegressionThresholds,
    build_case_result,
    build_evaluation_summary,
)
from payments_intelligence.evaluation.llm_judges import judge_agent_response
from payments_intelligence.evaluation.persistence import (
    DatabricksAgentEvaluationStore,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=("Run the EPIP M13 governed fraud-agent evaluation suite locally."))

    parser.add_argument("--profile", default="PAYMENTS_DEV")
    parser.add_argument("--catalog", default="payments_dev")
    parser.add_argument("--warehouse-id", default=None)
    parser.add_argument(
        "--search-endpoint-name",
        default="epip-dev-fraud-knowledge-search",
    )
    parser.add_argument(
        "--generation-model",
        default="claude-sonnet-4-6",
    )
    parser.add_argument(
        "--judge-model",
        default="gpt-4o-mini",
    )
    parser.add_argument(
        "--experiment-name",
        default="/Shared/epip-dev-fraud-agent-evaluation",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Optional smoke-test limit. Omit for the full formal suite.",
    )

    return parser.parse_args()


def require_environment_variable(name: str) -> str:
    value = os.environ.get(name)

    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")

    return value


def _log_case_to_mlflow(result: AgentEvaluationResult) -> None:
    mlflow.log_params(
        {
            "case_id": result.case_id,
            "scenario_type": result.scenario_type,
            "transaction_id": result.transaction_id,
            "agent_version": result.agent_version,
            "generation_model": result.generation_model,
            "judge_model": result.judge_model,
        }
    )

    mlflow.set_tags(
        {
            "epip.evaluation_run_id": result.evaluation_run_id,
            "epip.trace_id": result.trace_id or "",
            "epip.case_pass": str(result.case_pass).lower(),
        }
    )

    mlflow.log_metrics(
        {
            "tool_selection": result.deterministic.tool_selection,
            "tool_arguments": result.deterministic.tool_arguments,
            "tool_efficiency": result.deterministic.tool_efficiency,
            "scope_compliance": result.deterministic.scope_compliance,
            "structure": result.deterministic.structure,
            "citation": result.deterministic.citation,
            "human_review": result.deterministic.human_review,
            "safety": result.deterministic.safety,
            "groundedness": result.judge.groundedness,
            "evidence_completeness": result.judge.evidence_completeness,
            "investigation_quality": result.judge.investigation_quality,
            "risk_balance": result.judge.risk_balance,
            "uncertainty": result.judge.uncertainty,
            "duration_seconds": result.duration_seconds,
            "overall_score": result.overall_score,
            "case_pass": 1.0 if result.case_pass else 0.0,
        }
    )


def main() -> None:
    args = parse_args()

    require_environment_variable("ANTHROPIC_API_KEY")
    openai_api_key = require_environment_variable("OPENAI_API_KEY")

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

    store = DatabricksAgentEvaluationStore(
        settings=settings,
        warehouse_id=data_access.warehouse_id,
    )

    cases = store.load_active_cases(limit=args.max_cases)

    if not cases:
        raise RuntimeError("No active M13 golden evaluation cases were found. Run fraud_agent_evaluation_setup first.")

    judge_client = OpenAI(api_key=openai_api_key)
    evaluation_run_id = f"m13-{uuid4().hex}"
    thresholds = RegressionThresholds()

    print("Evaluation run ID:", evaluation_run_id)
    print("Cases:", len(cases))
    print("Generation model:", args.generation_model)
    print("Judge model:", args.judge_model)
    print("MLflow experiment:", args.experiment_name)
    print("SQL warehouse ID:", data_access.warehouse_id)

    case_results = []

    for case in cases:
        print("\n" + "=" * 88)
        print(case.case_id, "-", case.scenario_type)
        print("Transaction:", case.transaction_id)
        print("=" * 88)

        started = time.monotonic()

        agent_result = core.run_investigation_traced(
            transaction_id=case.transaction_id,
            investigator_question=case.investigator_question,
        )

        duration_seconds = time.monotonic() - started

        deterministic = score_deterministic(
            case=case,
            result=agent_result,
        )

        judge = judge_agent_response(
            client=judge_client,
            judge_model=args.judge_model,
            case=case,
            result=agent_result,
        )

        evaluation_result = build_case_result(
            evaluation_run_id=evaluation_run_id,
            case=case,
            result=agent_result,
            deterministic=deterministic,
            judge=judge,
            duration_seconds=duration_seconds,
            generation_model=args.generation_model,
            judge_model=args.judge_model,
            thresholds=thresholds,
        )

        with mlflow.start_run(run_name=f"{evaluation_run_id}-{case.case_id}"):
            _log_case_to_mlflow(evaluation_result)

        store.persist_result(evaluation_result)
        case_results.append(evaluation_result)

        print(
            json.dumps(
                {
                    "case_id": evaluation_result.case_id,
                    "tools_used": evaluation_result.tools_used,
                    "tool_call_count": evaluation_result.tool_call_count,
                    "trace_id": evaluation_result.trace_id,
                    "deterministic": (evaluation_result.deterministic.to_dict()),
                    "judge": evaluation_result.judge.to_dict(),
                    "overall_score": round(
                        evaluation_result.overall_score,
                        4,
                    ),
                    "case_pass": evaluation_result.case_pass,
                    "failure_reasons": (evaluation_result.failure_reasons),
                },
                indent=2,
                default=str,
            )
        )

    flush_traces = getattr(
        mlflow,
        "flush_trace_async_logging",
        None,
    )

    if callable(flush_traces):
        flush_traces()

    summary = build_evaluation_summary(
        case_results,
        thresholds=thresholds,
    )

    store.persist_summary(summary)

    print("\n" + "=" * 88)
    print("M13 EVALUATION SUMMARY")
    print("=" * 88)
    print(json.dumps(summary.to_dict(), indent=2, default=str))
    print("\nEPIP_M13_AGENT_EVALUATION_COMPLETE")
    print("REGRESSION_GATE=" + ("PASS" if summary.overall_pass else "FAIL"))

    if not summary.overall_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
