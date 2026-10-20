"""Tests for the independent, local synthetic benchmark slice."""

from benchmarks.financial_assurance.runner import (
    Delivery,
    Payment,
    build_fixture,
    controlled,
    evaluate,
    independent_oracle,
)


def test_controlled_output_matches_independent_oracle() -> None:
    source, deliveries = build_fixture()
    actual = {(item["transaction_id"], item["reason"]) for item in controlled(source, deliveries)}
    assert actual == independent_oracle()


def test_clean_settlements_have_no_exceptions() -> None:
    payments = [Payment("A", "1.00"), Payment("B", "2.00")]
    deliveries = [Delivery("B", "2.00"), Delivery("A", "1.00")]
    assert controlled(payments, deliveries) == []


def test_duplicate_valid_settlement_is_detected() -> None:
    payments = [Payment("A", "1.00")]
    deliveries = [Delivery("A", "1.00"), Delivery("A", "1.00")]
    assert controlled(payments, deliveries) == [
        {"transaction_id": "A", "reason": "DUPLICATE_DELIVERY"}
    ]


def test_fixture_metrics_and_pass_status() -> None:
    result = evaluate()
    assert result["passes_oracle"] is True
    assert result["metrics"]["precision"] == 1.0
    assert result["metrics"]["recall"] == 1.0
    assert result["execution_mode"] == "local_python_simulation"
