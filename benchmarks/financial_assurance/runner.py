"""First EPIP benchmark slice: duplicate delivery and settlement reconciliation.

Runs with the Python standard library; no Databricks, AWS or network access.
This is a simulation, NOT an execution test of the production Lakeflow pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class Payment:
    transaction_id: str
    amount: str
    currency: str = "USD"


@dataclass(frozen=True)
class Delivery:
    transaction_id: str
    amount: str
    currency: str = "USD"


def build_fixture() -> tuple[list[Payment], list[Delivery]]:
    """Deterministic fixture with duplicate, mismatch, missing and unexpected settlement."""
    source = [
        Payment("T001", "100.00"),
        Payment("T002", "250.00"),
        Payment("T003", "80.00"),
        Payment("T004", "120.00"),
    ]
    delivered = [
        Delivery("T001", "100.00"),
        Delivery("T002", "245.00"),
        Delivery("T004", "120.00"),
        Delivery("T004", "120.00"),
        Delivery("T999", "20.00"),
    ]
    return source, delivered


def baseline(source: list[Payment], delivered: list[Delivery]) -> dict[str, object]:
    """Transparent weak baseline: physical row counts and gross amount only.

    It is NOT intended to represent an industry-standard payment processor.
    """
    return {
        "source_count": len(source),
        "delivery_count": len(delivered),
        "gross_delivered_amount": str(sum((Decimal(d.amount) for d in delivered), Decimal(0))),
    }


def controlled(source: list[Payment], delivered: list[Delivery]) -> list[dict[str, str]]:
    """Compare each logical transaction to settlement deliveries; retain exception evidence."""
    source_by_id = {p.transaction_id: p for p in source}
    deliveries_by_id: dict[str, list[Delivery]] = {}
    for d in delivered:
        deliveries_by_id.setdefault(d.transaction_id, []).append(d)

    exceptions: list[dict[str, str]] = []
    for transaction_id, payment in sorted(source_by_id.items()):
        candidates = deliveries_by_id.pop(transaction_id, [])
        if not candidates:
            exceptions.append({"transaction_id": transaction_id, "reason": "MISSING_SETTLEMENT"})
            continue
        if len(candidates) > 1:
            exceptions.append({"transaction_id": transaction_id, "reason": "DUPLICATE_DELIVERY"})
        if any(Decimal(d.amount) != Decimal(payment.amount) or d.currency != payment.currency for d in candidates):
            exceptions.append({"transaction_id": transaction_id, "reason": "AMOUNT_OR_CURRENCY_MISMATCH"})
    for transaction_id in sorted(deliveries_by_id):
        exceptions.append({"transaction_id": transaction_id, "reason": "UNEXPECTED_SETTLEMENT"})
    return sorted(exceptions, key=lambda x: (x["transaction_id"], x["reason"]))


def independent_oracle() -> set[tuple[str, str]]:
    """Manually specified expected outcomes, independent of the evaluated algorithms."""
    return {
        ("T002", "AMOUNT_OR_CURRENCY_MISMATCH"),
        ("T003", "MISSING_SETTLEMENT"),
        ("T004", "DUPLICATE_DELIVERY"),
        ("T999", "UNEXPECTED_SETTLEMENT"),
    }


def evaluate() -> dict[str, object]:
    source, delivered = build_fixture()
    observed = controlled(source, delivered)
    actual = {(x["transaction_id"], x["reason"]) for x in observed}
    expected = independent_oracle()
    true_positive = len(actual & expected)
    false_positive = len(actual - expected)
    false_negative = len(expected - actual)
    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 1.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 1.0
    fixture_json = json.dumps({"source": [asdict(x) for x in source], "deliveries": [asdict(x) for x in delivered]}, sort_keys=True)
    return {
        "benchmark": "financial_assurance_v0.1",
        "execution_mode": "local_python_simulation",
        "fixture_sha256": hashlib.sha256(fixture_json.encode()).hexdigest(),
        "source_rows": len(source),
        "delivery_rows": len(delivered),
        "baseline": baseline(source, delivered),
        "controlled_exceptions": observed,
        "oracle_expected_exceptions": [
            {"transaction_id": tid, "reason": reason} for tid, reason in sorted(expected)
        ],
        "metrics": {
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "precision": precision,
            "recall": recall,
        },
        "passes_oracle": actual == expected,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Optional path for deterministic JSON results")
    args = parser.parse_args()
    result = evaluate()
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
    if not result["passes_oracle"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
