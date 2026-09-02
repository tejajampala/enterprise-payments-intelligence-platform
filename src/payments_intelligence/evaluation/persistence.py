"""Databricks SQL persistence for EPIP M13 agent evaluation."""

from __future__ import annotations

import json
from typing import Any

from databricks import sql
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

from payments_intelligence.agents.config import AgentSettings
from payments_intelligence.evaluation.contracts import (
    AgentEvaluationCase,
    AgentEvaluationResult,
    AgentEvaluationSummary,
)


class DatabricksAgentEvaluationStore:
    """Read golden cases and append evaluation history to governed Delta."""

    def __init__(
        self,
        settings: AgentSettings,
        warehouse_id: str | None = None,
    ) -> None:
        self.settings = settings
        self.workspace = WorkspaceClient(profile=settings.profile)
        self.warehouse_id = self._choose_sql_warehouse(warehouse_id)

        self.config = Config(
            profile=settings.profile,
            warehouse_id=self.warehouse_id,
        )

        headers = self.config.authenticate()
        authorization = headers.get("Authorization", "")

        if not authorization.startswith("Bearer "):
            raise RuntimeError("Databricks profile did not provide a Bearer authentication token")

        self._access_token = authorization.removeprefix("Bearer ").strip()

        if not self.config.sql_http_path:
            raise RuntimeError("Unable to determine SQL warehouse HTTP path")

    @property
    def evaluation_dataset_table(self) -> str:
        return f"{self.settings.catalog}.{self.settings.ai_schema}.agent_evaluation_dataset"

    @property
    def evaluation_results_table(self) -> str:
        return f"{self.settings.catalog}.{self.settings.ai_schema}.agent_evaluation_results"

    @property
    def evaluation_summary_table(self) -> str:
        return f"{self.settings.catalog}.{self.settings.ai_schema}.agent_evaluation_summary"

    def _choose_sql_warehouse(
        self,
        explicit_warehouse_id: str | None,
    ) -> str:
        if explicit_warehouse_id:
            return explicit_warehouse_id

        warehouses = list(self.workspace.warehouses.list())

        if not warehouses:
            raise RuntimeError("No Databricks SQL warehouse is available")

        running = [warehouse for warehouse in warehouses if "RUNNING" in str(getattr(warehouse, "state", "")).upper()]

        selected = running[0] if running else warehouses[0]
        selected_id = getattr(selected, "id", None)

        if not selected_id:
            raise RuntimeError("Unable to determine SQL warehouse ID")

        return str(selected_id)

    def _sql_connection(self) -> Any:
        return sql.connect(
            server_hostname=self.config.hostname,
            http_path=self.config.sql_http_path,
            access_token=self._access_token,
            use_cloud_fetch=False,
            user_agent_entry="epip-m13-agent-evaluation",
        )

    @staticmethod
    def _rows_as_dicts(cursor: Any) -> list[dict[str, Any]]:
        if cursor.description is None:
            return []

        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]

    def load_active_cases(
        self,
        limit: int | None = None,
    ) -> list[AgentEvaluationCase]:
        """Load governed active golden cases."""

        statement = f"""
        SELECT
            case_id,
            scenario_type,
            transaction_id,
            investigator_question,
            to_json(required_tools) AS required_tools_json,
            to_json(allowed_tools) AS allowed_tools_json,
            to_json(forbidden_tools) AS forbidden_tools_json,
            max_expected_tool_calls,
            knowledge_required,
            citations_required,
            expected_behavior,
            forbidden_behavior
        FROM {self.evaluation_dataset_table}
        WHERE active = true
        ORDER BY case_id
        """

        if limit is not None:
            if limit < 1:
                raise ValueError("limit must be positive")

            statement += f"\nLIMIT {int(limit)}"

        with (
            self._sql_connection() as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(statement)
            rows = self._rows_as_dicts(cursor)

        return [
            AgentEvaluationCase(
                case_id=str(row["case_id"]),
                scenario_type=str(row["scenario_type"]),
                transaction_id=str(row["transaction_id"]),
                investigator_question=str(row["investigator_question"]),
                required_tools=tuple(str(value) for value in json.loads(str(row["required_tools_json"] or "[]"))),
                allowed_tools=tuple(str(value) for value in json.loads(str(row["allowed_tools_json"] or "[]"))),
                forbidden_tools=tuple(str(value) for value in json.loads(str(row["forbidden_tools_json"] or "[]"))),
                max_expected_tool_calls=int(row["max_expected_tool_calls"]),
                knowledge_required=bool(row["knowledge_required"]),
                citations_required=bool(row["citations_required"]),
                expected_behavior=str(row["expected_behavior"]),
                forbidden_behavior=str(row["forbidden_behavior"]),
            )
            for row in rows
        ]

    def persist_result(
        self,
        result: AgentEvaluationResult,
    ) -> None:
        """Append one evaluation-case result."""

        statement = f"""
        INSERT INTO {self.evaluation_results_table} (
            evaluation_run_id,
            case_id,
            scenario_type,
            transaction_id,
            agent_version,
            generation_model,
            judge_model,
            trace_id,
            tools_used,
            tool_call_count,
            tool_selection_score,
            tool_argument_score,
            tool_efficiency_score,
            scope_compliance_score,
            structure_score,
            citation_score,
            human_review_score,
            safety_score,
            groundedness_score,
            evidence_completeness_score,
            investigation_quality_score,
            risk_balance_score,
            uncertainty_score,
            judge_rationale,
            duration_seconds,
            overall_score,
            case_pass,
            failure_reasons,
            created_at
        )
        SELECT
            ?, ?, ?, ?, ?, ?, ?, ?,
            from_json(?, 'ARRAY<STRING>'),
            ?,
            ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?,
            ?, ?, ?,
            from_json(?, 'ARRAY<STRING>'),
            current_timestamp()
        """

        parameters: list[Any] = [
            result.evaluation_run_id,
            result.case_id,
            result.scenario_type,
            result.transaction_id,
            result.agent_version,
            result.generation_model,
            result.judge_model,
            result.trace_id,
            json.dumps(list(result.tools_used)),
            result.tool_call_count,
            result.deterministic.tool_selection,
            result.deterministic.tool_arguments,
            result.deterministic.tool_efficiency,
            result.deterministic.scope_compliance,
            result.deterministic.structure,
            result.deterministic.citation,
            result.deterministic.human_review,
            result.deterministic.safety,
            result.judge.groundedness,
            result.judge.evidence_completeness,
            result.judge.investigation_quality,
            result.judge.risk_balance,
            result.judge.uncertainty,
            result.judge.rationale,
            result.duration_seconds,
            result.overall_score,
            result.case_pass,
            json.dumps(list(result.failure_reasons)),
        ]

        with (
            self._sql_connection() as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(statement, parameters)

    def persist_summary(
        self,
        summary: AgentEvaluationSummary,
    ) -> None:
        """Append one aggregate evaluation-run summary."""

        statement = f"""
        INSERT INTO {self.evaluation_summary_table} (
            evaluation_run_id,
            agent_version,
            generation_model,
            judge_model,
            case_count,
            passed_cases,
            failed_cases,
            pass_rate,
            avg_tool_selection_score,
            avg_tool_argument_score,
            avg_tool_efficiency_score,
            avg_groundedness_score,
            avg_evidence_completeness_score,
            avg_investigation_quality_score,
            avg_citation_score,
            scope_compliance_rate,
            human_review_rate,
            safety_rate,
            structure_compliance_rate,
            avg_duration_seconds,
            overall_pass,
            failed_gates,
            created_at
        )
        SELECT
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?,
            from_json(?, 'ARRAY<STRING>'),
            current_timestamp()
        """

        parameters: list[Any] = [
            summary.evaluation_run_id,
            summary.agent_version,
            summary.generation_model,
            summary.judge_model,
            summary.case_count,
            summary.passed_cases,
            summary.failed_cases,
            summary.pass_rate,
            summary.avg_tool_selection_score,
            summary.avg_tool_argument_score,
            summary.avg_tool_efficiency_score,
            summary.avg_groundedness_score,
            summary.avg_evidence_completeness_score,
            summary.avg_investigation_quality_score,
            summary.avg_citation_score,
            summary.scope_compliance_rate,
            summary.human_review_rate,
            summary.safety_rate,
            summary.structure_compliance_rate,
            summary.avg_duration_seconds,
            summary.overall_pass,
            json.dumps(list(summary.failed_gates)),
        ]

        with (
            self._sql_connection() as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(statement, parameters)
