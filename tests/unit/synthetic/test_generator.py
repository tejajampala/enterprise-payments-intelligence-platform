"""Tests for deterministic synthetic payments data generation."""

from payments_intelligence.synthetic import (
    SyntheticDataConfig,
    SyntheticDataGenerator,
)


def small_config(seed: int = 42) -> SyntheticDataConfig:
    return SyntheticDataConfig(
        seed=seed,
        customer_count=10,
        accounts_per_customer_min=1,
        accounts_per_customer_max=2,
        merchant_count=5,
        transaction_count=50,
        suspicious_transaction_rate=0.10,
    )


def test_generator_is_deterministic_for_same_seed() -> None:
    first = SyntheticDataGenerator(small_config(seed=42)).generate()
    second = SyntheticDataGenerator(small_config(seed=42)).generate()

    assert first == second


def test_different_seed_changes_generated_data() -> None:
    first = SyntheticDataGenerator(small_config(seed=42)).generate()
    second = SyntheticDataGenerator(small_config(seed=99)).generate()

    assert first != second


def test_expected_entity_counts_are_generated() -> None:
    dataset = SyntheticDataGenerator(small_config()).generate()

    assert len(dataset.customers) == 10
    assert len(dataset.merchants) == 5
    assert len(dataset.transactions) == 50

    assert 10 <= len(dataset.accounts) <= 20

    assert len(dataset.payment_events) == 100


def test_account_customer_references_are_valid() -> None:
    dataset = SyntheticDataGenerator(small_config()).generate()

    customer_ids = {customer.customer_id for customer in dataset.customers}

    for account in dataset.accounts:
        assert account.customer_id in customer_ids


def test_transaction_references_are_valid() -> None:
    dataset = SyntheticDataGenerator(small_config()).generate()

    account_ids = {account.account_id for account in dataset.accounts}

    merchant_ids = {merchant.merchant_id for merchant in dataset.merchants}

    for transaction in dataset.transactions:
        assert transaction.account_id in account_ids
        assert transaction.merchant_id in merchant_ids


def test_payment_event_references_are_valid() -> None:
    dataset = SyntheticDataGenerator(small_config()).generate()

    transaction_ids = {transaction.transaction_id for transaction in dataset.transactions}

    for event in dataset.payment_events:
        assert event.transaction.transaction_id in transaction_ids


def test_each_transaction_has_two_lifecycle_events() -> None:
    dataset = SyntheticDataGenerator(small_config()).generate()

    events_by_transaction: dict[str, list[int]] = {}

    for event in dataset.payment_events:
        transaction_id = event.transaction.transaction_id

        events_by_transaction.setdefault(
            transaction_id,
            [],
        ).append(event.sequence_number)

    assert len(events_by_transaction) == len(dataset.transactions)

    for sequence_numbers in events_by_transaction.values():
        assert sequence_numbers == [1, 2]


def test_event_ids_are_unique() -> None:
    dataset = SyntheticDataGenerator(small_config()).generate()

    event_ids = [event.event_id for event in dataset.payment_events]

    assert len(event_ids) == len(set(event_ids))


def test_fraud_cases_reference_existing_transactions() -> None:
    dataset = SyntheticDataGenerator(small_config()).generate()

    transaction_ids = {transaction.transaction_id for transaction in dataset.transactions}

    for fraud_case in dataset.fraud_cases:
        assert fraud_case.transaction_id in transaction_ids


def test_generator_produces_some_fraud_cases() -> None:
    config = SyntheticDataConfig(
        seed=42,
        customer_count=10,
        merchant_count=5,
        transaction_count=200,
        suspicious_transaction_rate=0.20,
    )

    dataset = SyntheticDataGenerator(config).generate()

    assert len(dataset.fraud_cases) > 0


def test_dataset_summary_contains_record_counts() -> None:
    dataset = SyntheticDataGenerator(small_config()).generate()

    summary = dataset.summary()

    assert summary["customers"] == 10
    assert summary["merchants"] == 5
    assert summary["transactions"] == 50


def test_invalid_suspicious_rate_is_rejected() -> None:
    try:
        SyntheticDataConfig(
            suspicious_transaction_rate=1.5,
        )
    except ValueError as error:
        assert "between 0 and 1" in str(error)
    else:
        raise AssertionError("Expected invalid suspicious transaction rate to fail")
