"""Unit tests for canonical payments domain models."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from payments_intelligence.domain.enums import (
    CustomerStatus,
    FraudCaseStatus,
    FraudOutcome,
    KycStatus,
    PaymentChannel,
    PaymentEventType,
    PaymentMethod,
    RiskRating,
    TransactionStatus,
)
from payments_intelligence.domain.models import (
    Customer,
    FraudCase,
    PaymentEvent,
    PaymentTransaction,
)


def build_transaction() -> PaymentTransaction:
    return PaymentTransaction(
        transaction_id="txn-000001",
        account_id="acct-000001",
        merchant_id="merchant-000001",
        event_timestamp=datetime(2026, 8, 19, 10, 30, tzinfo=UTC),
        amount=Decimal("125.50"),
        currency="AUD",
        channel=PaymentChannel.ECOMMERCE,
        payment_method=PaymentMethod.CREDIT_CARD,
        status=TransactionStatus.AUTHORIZED,
        card_present=False,
        device_id="device-100",
        ip_address="203.0.113.10",
        country="AU",
    )


def test_valid_transaction_can_be_created() -> None:
    transaction = build_transaction()

    assert transaction.transaction_id == "txn-000001"
    assert transaction.amount == Decimal("125.50")
    assert transaction.currency == "AUD"


def test_transaction_rejects_zero_amount() -> None:
    with pytest.raises(ValueError, match="amount must be greater than zero"):
        PaymentTransaction(
            transaction_id="txn-000002",
            account_id="acct-000001",
            merchant_id="merchant-000001",
            event_timestamp=datetime(2026, 8, 19, 10, 30, tzinfo=UTC),
            amount=Decimal("0"),
            currency="AUD",
            channel=PaymentChannel.POS,
            payment_method=PaymentMethod.DEBIT_CARD,
            status=TransactionStatus.DECLINED,
            card_present=True,
            device_id=None,
            ip_address=None,
            country="AU",
        )


def test_transaction_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="event_timestamp must be timezone-aware"):
        PaymentTransaction(
            transaction_id="txn-000003",
            account_id="acct-000001",
            merchant_id="merchant-000001",
            event_timestamp=datetime(2026, 8, 19, 10, 30),
            amount=Decimal("20.00"),
            currency="AUD",
            channel=PaymentChannel.MOBILE,
            payment_method=PaymentMethod.DIGITAL_WALLET,
            status=TransactionStatus.AUTHORIZED,
            card_present=False,
            device_id="device-200",
            ip_address="203.0.113.11",
            country="AU",
        )


def test_customer_contains_fields_required_for_future_cdc() -> None:
    customer = Customer(
        customer_id="cust-000001",
        first_name="Alex",
        last_name="Taylor",
        date_of_birth=date(1985, 5, 10),
        email="alex.taylor@example.com",
        phone="+61400000000",
        address_line_1="100 Example Street",
        city="Melbourne",
        state="VIC",
        postcode="3000",
        country="AU",
        risk_rating=RiskRating.LOW,
        kyc_status=KycStatus.VERIFIED,
        status=CustomerStatus.ACTIVE,
        record_version=1,
        source_updated_at=datetime(2026, 8, 19, 10, 0, tzinfo=UTC),
    )

    assert customer.record_version == 1
    assert customer.is_deleted is False


def test_payment_event_requires_positive_sequence_number() -> None:
    with pytest.raises(
        ValueError,
        match="sequence_number must be greater than or equal to 1",
    ):
        PaymentEvent(
            event_id="event-1",
            event_type=PaymentEventType.AUTHORIZATION,
            event_timestamp=datetime(2026, 8, 19, 10, 30, tzinfo=UTC),
            sequence_number=0,
            transaction=build_transaction(),
        )


def test_fraud_label_is_not_embedded_in_transaction() -> None:
    transaction = build_transaction()

    assert not hasattr(transaction, "is_fraud")


def test_fraud_case_captures_confirmed_outcome() -> None:
    fraud_case = FraudCase(
        case_id="case-000001",
        transaction_id="txn-000001",
        opened_at=datetime(2026, 8, 19, 11, 0, tzinfo=UTC),
        status=FraudCaseStatus.CLOSED,
        suspected_reason="Unusual device and transaction velocity",
        outcome=FraudOutcome.CONFIRMED_FRAUD,
        analyst_notes="Customer confirmed that the payment was unauthorized.",
        closed_at=datetime(2026, 8, 19, 12, 30, tzinfo=UTC),
    )

    assert fraud_case.outcome is FraudOutcome.CONFIRMED_FRAUD


def test_fraud_case_rejects_invalid_close_time() -> None:
    with pytest.raises(ValueError, match="closed_at must not be before opened_at"):
        FraudCase(
            case_id="case-000002",
            transaction_id="txn-000002",
            opened_at=datetime(2026, 8, 19, 12, 0, tzinfo=UTC),
            status=FraudCaseStatus.CLOSED,
            suspected_reason="Velocity threshold exceeded",
            outcome=FraudOutcome.LEGITIMATE,
            closed_at=datetime(2026, 8, 19, 11, 0, tzinfo=UTC),
        )
