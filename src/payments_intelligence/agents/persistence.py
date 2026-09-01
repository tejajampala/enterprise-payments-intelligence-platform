"""Governed persistence for successful EPIP fraud-agent investigations."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from databricks import sql
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

from payments_intelligence.agents.config import (
    AgentSettings,
    validate_transaction_id,
)
from payments_intelligence.agents.contracts import (
    AgentRunResult,
)

_SECTION_HEADINGS = (
    "Investigation Assessment",
    "Risk Indicators",
    "Counter-Indicators",
    "Model Signal",
    "Evidence Reviewed",
    "Knowledge Sources",
    "Limitations",
    "Recommended Next Steps",
)

_FORBIDDEN_PERSISTENCE_KEYS = {
    "block_card",
    "decline_transaction",
    "fraud_decision",
    "fraud_outcome",
    "freeze_account",
    "is_confirmed_fraud",
}


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationSections:
    """Structured sections parsed from the user-visible response."""

    assessment: str

    risk_indicators: tuple[str, ...]

    counter_indicators: tuple[str, ...]

    model_signal: str

    evidence_reviewed: tuple[str, ...]

    knowledge_sources: tuple[str, ...]

    limitations: str

    recommended_next_steps: tuple[str, ...]

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return asdict(self)


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationPersistenceRecord:
    """Validated governed investigation-history record."""

    investigation_id: str

    transaction_id: str

    agent_version: str

    generation_provider: str

    generation_model: str

    tools_used: tuple[str, ...]

    tool_call_count: int

    assessment: str

    risk_indicators: tuple[str, ...]

    counter_indicators: tuple[str, ...]

    model_signal: str

    evidence_reviewed: tuple[str, ...]

    knowledge_sources: tuple[str, ...]

    limitations: str

    recommended_next_steps: tuple[str, ...]

    final_response: str

    tool_execution_json: str

    trace_id: str | None

    duration_seconds: float

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return asdict(self)


def _clean_line(
    value: str,
) -> str:
    """Normalize one markdown list line."""

    line = value.strip()

    line = re.sub(
        r"^[-*+]\s+",
        "",
        line,
    )

    line = re.sub(
        r"^\d+[.)]\s+",
        "",
        line,
    )

    return line.strip()


def _list_items(
    section_text: str,
) -> tuple[str, ...]:
    """Parse one markdown section into items."""

    items = [_clean_line(line) for line in section_text.splitlines() if _clean_line(line)]

    return tuple(items)


def parse_investigation_sections(
    final_text: str,
) -> InvestigationSections:
    """Parse the stable M12 markdown response contract."""

    if not final_text.strip():
        raise ValueError("final_text cannot be empty")

    heading_pattern = re.compile(
        r"^##\s+(" + "|".join(re.escape(heading) for heading in _SECTION_HEADINGS) + r")\s*$",
        flags=re.MULTILINE,
    )

    matches = list(heading_pattern.finditer(final_text))

    sections: dict[
        str,
        str,
    ] = {}

    for index, match in enumerate(matches):
        start = match.end()

        end = matches[index + 1].start() if index + 1 < len(matches) else len(final_text)

        sections[match.group(1)] = final_text[start:end].strip()

    return InvestigationSections(
        assessment=sections.get(
            "Investigation Assessment",
            "",
        ).strip(),
        risk_indicators=_list_items(
            sections.get(
                "Risk Indicators",
                "",
            )
        ),
        counter_indicators=_list_items(
            sections.get(
                "Counter-Indicators",
                "",
            )
        ),
        model_signal=sections.get(
            "Model Signal",
            "",
        ).strip(),
        evidence_reviewed=_list_items(
            sections.get(
                "Evidence Reviewed",
                "",
            )
        ),
        knowledge_sources=_list_items(
            sections.get(
                "Knowledge Sources",
                "",
            )
        ),
        limitations=sections.get(
            "Limitations",
            "",
        ).strip(),
        recommended_next_steps=_list_items(
            sections.get(
                "Recommended Next Steps",
                "",
            )
        ),
    )


def build_persistence_record(
    result: AgentRunResult,
    duration_seconds: float,
    agent_version: str = "m12-v1",
) -> InvestigationPersistenceRecord:
    """Build one governed persistence record."""

    if duration_seconds < 0:
        raise ValueError("duration_seconds cannot be negative")

    transaction_id = validate_transaction_id(result.transaction_id)

    sections = parse_investigation_sections(result.final_text)

    record = InvestigationPersistenceRecord(
        investigation_id=str(uuid4()),
        transaction_id=transaction_id,
        agent_version=agent_version,
        generation_provider="anthropic",
        generation_model=(result.generation_model),
        tools_used=tuple(result.tools_used),
        tool_call_count=(result.tool_call_count),
        assessment=(sections.assessment),
        risk_indicators=(sections.risk_indicators),
        counter_indicators=(sections.counter_indicators),
        model_signal=(sections.model_signal),
        evidence_reviewed=(sections.evidence_reviewed),
        knowledge_sources=(sections.knowledge_sources),
        limitations=(sections.limitations),
        recommended_next_steps=(sections.recommended_next_steps),
        final_response=(result.final_text),
        tool_execution_json=json.dumps(
            [tool_record.to_dict() for tool_record in result.tool_calls],
            sort_keys=True,
            default=str,
        ),
        trace_id=result.trace_id,
        duration_seconds=float(duration_seconds),
    )

    prohibited = _FORBIDDEN_PERSISTENCE_KEYS.intersection(record.to_dict())

    if prohibited:
        raise RuntimeError(f"Persistence record contains prohibited keys: {sorted(prohibited)}")

    return record


class DatabricksInvestigationPersistence:
    """Append successful investigations to governed Delta."""

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

        authorization = headers.get(
            "Authorization",
            "",
        )

        if not authorization.startswith("Bearer "):
            raise RuntimeError("Databricks profile did not provide a Bearer authentication token")

        self._access_token = authorization.removeprefix("Bearer ").strip()

        if not self.config.sql_http_path:
            raise RuntimeError("Unable to determine SQL warehouse HTTP path")

    @property
    def investigation_table(
        self,
    ) -> str:

        return f"{self.settings.catalog}.{self.settings.ai_schema}.fraud_agent_investigations"

    def _choose_sql_warehouse(
        self,
        explicit_warehouse_id: str | None,
    ) -> str:

        if explicit_warehouse_id:
            return explicit_warehouse_id

        warehouses = list(self.workspace.warehouses.list())

        if not warehouses:
            raise RuntimeError("No Databricks SQL warehouse is available")

        running = [
            warehouse
            for warehouse in warehouses
            if "RUNNING"
            in str(
                getattr(
                    warehouse,
                    "state",
                    "",
                )
            ).upper()
        ]

        selected = running[0] if running else warehouses[0]

        selected_id = getattr(
            selected,
            "id",
            None,
        )

        if not selected_id:
            raise RuntimeError("Unable to determine SQL warehouse ID")

        return str(selected_id)

    def _sql_connection(
        self,
    ) -> Any:

        return sql.connect(
            server_hostname=(self.config.hostname),
            http_path=(self.config.sql_http_path),
            access_token=(self._access_token),
            use_cloud_fetch=False,
            user_agent_entry=("epip-m12-fraud-agent-persistence"),
        )

    def persist(
        self,
        record: InvestigationPersistenceRecord,
    ) -> str:
        """Append one successful investigation."""

        statement = f"""
        INSERT INTO
            {self.investigation_table} (

                investigation_id,
                transaction_id,

                agent_version,
                generation_provider,
                generation_model,

                tools_used,
                tool_call_count,

                assessment,
                risk_indicators,
                counter_indicators,
                model_signal,

                evidence_reviewed,
                knowledge_sources,

                limitations,
                recommended_next_steps,

                final_response,
                tool_execution_json,

                trace_id,
                duration_seconds,
                created_at
            )

        SELECT

            ?,
            ?,

            ?,
            ?,
            ?,

            from_json(
                ?,
                'ARRAY<STRING>'
            ),

            ?,

            ?,

            from_json(
                ?,
                'ARRAY<STRING>'
            ),

            from_json(
                ?,
                'ARRAY<STRING>'
            ),

            ?,

            from_json(
                ?,
                'ARRAY<STRING>'
            ),

            from_json(
                ?,
                'ARRAY<STRING>'
            ),

            ?,

            from_json(
                ?,
                'ARRAY<STRING>'
            ),

            ?,
            ?,

            ?,
            ?,

            current_timestamp()
        """

        parameters: list[Any] = [
            record.investigation_id,
            record.transaction_id,
            record.agent_version,
            record.generation_provider,
            record.generation_model,
            json.dumps(list(record.tools_used)),
            record.tool_call_count,
            record.assessment,
            json.dumps(list(record.risk_indicators)),
            json.dumps(list(record.counter_indicators)),
            record.model_signal,
            json.dumps(list(record.evidence_reviewed)),
            json.dumps(list(record.knowledge_sources)),
            record.limitations,
            json.dumps(list(record.recommended_next_steps)),
            record.final_response,
            record.tool_execution_json,
            record.trace_id,
            record.duration_seconds,
        ]

        with (
            self._sql_connection() as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                statement,
                parameters,
            )

        return record.investigation_id
