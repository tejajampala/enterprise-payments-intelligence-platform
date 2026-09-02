"""Structured OpenAI judge for EPIP M13 fraud-agent evaluation."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from payments_intelligence.agents.contracts import AgentRunResult
from payments_intelligence.evaluation.contracts import (
    AgentEvaluationCase,
    JudgeScores,
)

_JUDGE_SYSTEM_PROMPT = """
You are evaluating a fraud-investigation assistant in a synthetic enterprise
payments platform.

Evaluate only the evidence supplied in this request. Do not introduce outside
facts. The assistant is an investigation aid, not an autonomous fraud-decision
system.

Return JSON only with exactly these keys:
groundedness
evidence_completeness
investigation_quality
risk_balance
uncertainty
rationale

All five scores must be numbers from 0.0 to 1.0.

Definitions:
- groundedness: claims are supported by tool evidence and retrieved knowledge.
- evidence_completeness: material available evidence is considered rather than ignored.
- investigation_quality: the assessment is useful, coherent, cautious, and actionable for a human investigator.
- risk_balance: risk indicators and counter-indicators are balanced when evidence supports both.
- uncertainty: limitations and uncertainty are calibrated; the answer avoids unsupported certainty.

Hard principles:
- A fraud-model score is a signal, not proof.
- Cross-border activity alone is not proof of fraud.
- Duplicate Kafka/message delivery is not automatically multiple financial transactions.
- The assistant must not claim to block cards, freeze accounts, decline payments,
  modify cases, or make the final fraud decision.
""".strip()


def _clamp_score(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Judge returned non-numeric score: {value!r}") from exc

    return max(0.0, min(1.0, numeric))


def _tool_evidence(result: AgentRunResult) -> list[dict[str, Any]]:
    return [
        {
            "tool_name": record.tool_name,
            "arguments": record.arguments,
            "result": record.result,
        }
        for record in result.tool_calls
    ]


def judge_agent_response(
    client: OpenAI,
    judge_model: str,
    case: AgentEvaluationCase,
    result: AgentRunResult,
) -> JudgeScores:
    """Judge one complete agent response using only captured evidence."""

    judge_payload = {
        "case": {
            "case_id": case.case_id,
            "scenario_type": case.scenario_type,
            "transaction_id": case.transaction_id,
            "investigator_question": case.investigator_question,
            "expected_behavior": case.expected_behavior,
            "forbidden_behavior": case.forbidden_behavior,
        },
        "tool_evidence": _tool_evidence(result),
        "final_response": result.final_text,
    }

    response = client.chat.completions.create(
        model=judge_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": _JUDGE_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": json.dumps(
                    judge_payload,
                    sort_keys=True,
                    default=str,
                ),
            },
        ],
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError("OpenAI judge returned an empty response")

    parsed = json.loads(content)

    return JudgeScores(
        groundedness=_clamp_score(parsed.get("groundedness")),
        evidence_completeness=_clamp_score(parsed.get("evidence_completeness")),
        investigation_quality=_clamp_score(parsed.get("investigation_quality")),
        risk_balance=_clamp_score(parsed.get("risk_balance")),
        uncertainty=_clamp_score(parsed.get("uncertainty")),
        rationale=str(parsed.get("rationale") or "").strip(),
    )
