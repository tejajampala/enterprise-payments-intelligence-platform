"""Tests for controlled synthetic data scenarios."""

from datetime import timedelta

from payments_intelligence.domain.enums import (
    AccountStatus,
    MerchantStatus,
    RiskRating,
)
from payments_intelligence.synthetic import (
    DataQualityIssue,
    DeliveryScenario,
    SyntheticDataConfig,
    SyntheticDataGenerator,
    SyntheticScenarioBuilder,
)


def build_scenarios():
    config = SyntheticDataConfig(
        seed=42,
        customer_count=10,
        merchant_count=5,
        transaction_count=50,
    )

    dataset = SyntheticDataGenerator(config).generate()
    scenarios = SyntheticScenarioBuilder(dataset).build()

    return dataset, scenarios


def test_customer_cdc_contains_three_versions() -> None:
    _, scenarios = build_scenarios()

    records = scenarios.customer_cdc_records

    assert len(records) == 3

    assert {record.record_version for record in records} == {1, 2, 3}


def test_customer_cdc_is_delivered_out_of_order() -> None:
    _, scenarios = build_scenarios()

    versions = [customer.record_version for customer in scenarios.customer_cdc_records]

    assert versions == [1, 3, 2]


def test_customer_delete_is_soft_delete() -> None:
    _, scenarios = build_scenarios()

    version_three = next(
        customer for customer in scenarios.customer_cdc_records if customer.record_version == 3
    )

    assert version_three.is_deleted is True


def test_customer_update_changes_address() -> None:
    _, scenarios = build_scenarios()

    version_two = next(
        customer for customer in scenarios.customer_cdc_records if customer.record_version == 2
    )

    assert version_two.city == "Sydney"
    assert version_two.state == "NSW"
    assert version_two.postcode == "2000"


def test_account_status_change_is_generated() -> None:
    _, scenarios = build_scenarios()

    original, updated = scenarios.account_cdc_records

    assert original.record_version == 1
    assert updated.record_version == 2
    assert updated.status is AccountStatus.BLOCKED


def test_merchant_risk_change_is_generated() -> None:
    _, scenarios = build_scenarios()

    original, updated = scenarios.merchant_cdc_records

    assert original.record_version == 1
    assert updated.record_version == 2
    assert updated.risk_rating is RiskRating.HIGH
    assert updated.status is MerchantStatus.SUSPENDED


def test_duplicate_transaction_has_same_business_key() -> None:
    _, scenarios = build_scenarios()

    first, duplicate = scenarios.duplicate_transactions

    assert first == duplicate
    assert first.transaction_id == duplicate.transaction_id


def test_duplicate_event_id_is_delivered_twice() -> None:
    _, scenarios = build_scenarios()

    event_ids = [delivery.event.event_id for delivery in scenarios.event_deliveries]

    assert len(event_ids) > len(set(event_ids))


def test_out_of_order_event_arrives_sequence_two_before_one() -> None:
    _, scenarios = build_scenarios()

    deliveries = [
        delivery
        for delivery in scenarios.event_deliveries
        if delivery.scenario is DeliveryScenario.OUT_OF_ORDER
    ]

    assert len(deliveries) == 2

    assert [delivery.event.sequence_number for delivery in deliveries] == [2, 1]

    assert (
        deliveries[0].event.transaction.transaction_id
        == deliveries[1].event.transaction.transaction_id
    )


def test_late_event_arrives_four_hours_after_event_time() -> None:
    _, scenarios = build_scenarios()

    late_delivery = next(
        delivery
        for delivery in scenarios.event_deliveries
        if delivery.scenario is DeliveryScenario.LATE
    )

    assert late_delivery.arrived_at - late_delivery.event.event_timestamp == timedelta(hours=4)


def test_invalid_raw_records_cover_expected_quality_issues() -> None:
    _, scenarios = build_scenarios()

    issues = {record.issue for record in scenarios.invalid_transaction_records}

    assert issues == {
        DataQualityIssue.MISSING_TRANSACTION_ID,
        DataQualityIssue.NEGATIVE_AMOUNT,
        DataQualityIssue.INVALID_CURRENCY,
        DataQualityIssue.ORPHAN_ACCOUNT,
    }


def test_missing_transaction_id_scenario_contains_null() -> None:
    _, scenarios = build_scenarios()

    record = next(
        record
        for record in scenarios.invalid_transaction_records
        if record.issue is DataQualityIssue.MISSING_TRANSACTION_ID
    )

    assert record.payload["transaction_id"] is None


def test_orphan_account_reference_does_not_exist() -> None:
    dataset, scenarios = build_scenarios()

    valid_account_ids = {account.account_id for account in dataset.accounts}

    record = next(
        record
        for record in scenarios.invalid_transaction_records
        if record.issue is DataQualityIssue.ORPHAN_ACCOUNT
    )

    assert record.payload["account_id"] not in valid_account_ids


def test_scenario_summary_contains_expected_counts() -> None:
    _, scenarios = build_scenarios()

    summary = scenarios.summary()

    assert summary["customer_cdc_records"] == 3
    assert summary["account_cdc_records"] == 2
    assert summary["merchant_cdc_records"] == 2
    assert summary["duplicate_transactions"] == 2
    assert summary["event_deliveries"] == 6
    assert summary["invalid_transaction_records"] == 4
