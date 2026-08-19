"""Controlled CDC, data-quality, and streaming scenarios."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from payments_intelligence.domain.enums import (
    AccountStatus,
    MerchantStatus,
    RiskRating,
)
from payments_intelligence.domain.models import (
    Account,
    Customer,
    Merchant,
    PaymentEvent,
    PaymentTransaction,
)
from payments_intelligence.synthetic.generator import SyntheticDataSet


class DataQualityIssue(StrEnum):
    """Known malformed raw-record scenarios."""

    MISSING_TRANSACTION_ID = "MISSING_TRANSACTION_ID"
    NEGATIVE_AMOUNT = "NEGATIVE_AMOUNT"
    INVALID_CURRENCY = "INVALID_CURRENCY"
    ORPHAN_ACCOUNT = "ORPHAN_ACCOUNT"


class DeliveryScenario(StrEnum):
    """Streaming delivery behaviour applied to an event."""

    NORMAL = "NORMAL"
    DUPLICATE = "DUPLICATE"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    LATE = "LATE"


@dataclass(frozen=True, slots=True)
class InvalidRawRecord:
    """Raw source payload containing an intentional data-quality defect."""

    issue: DataQualityIssue
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class PaymentEventDelivery:
    """Represents when a payment event is delivered to the streaming platform."""

    event: PaymentEvent
    arrived_at: datetime
    scenario: DeliveryScenario


@dataclass(frozen=True, slots=True)
class SyntheticScenarioSet:
    """Controlled anomalies layered on top of a clean synthetic dataset."""

    customer_cdc_records: tuple[Customer, ...]
    account_cdc_records: tuple[Account, ...]
    merchant_cdc_records: tuple[Merchant, ...]

    duplicate_transactions: tuple[PaymentTransaction, ...]

    event_deliveries: tuple[PaymentEventDelivery, ...]

    invalid_transaction_records: tuple[InvalidRawRecord, ...]

    def summary(self) -> dict[str, int]:
        """Return counts of generated scenario records."""

        return {
            "customer_cdc_records": len(self.customer_cdc_records),
            "account_cdc_records": len(self.account_cdc_records),
            "merchant_cdc_records": len(self.merchant_cdc_records),
            "duplicate_transactions": len(self.duplicate_transactions),
            "event_deliveries": len(self.event_deliveries),
            "invalid_transaction_records": len(self.invalid_transaction_records),
        }


class SyntheticScenarioBuilder:
    """Build controlled enterprise data scenarios from a clean dataset."""

    def __init__(self, dataset: SyntheticDataSet) -> None:
        self.dataset = dataset

    def build(self) -> SyntheticScenarioSet:
        """Build all supported controlled scenarios."""

        if len(self.dataset.customers) < 1:
            raise ValueError("dataset must contain at least one customer")

        if len(self.dataset.accounts) < 1:
            raise ValueError("dataset must contain at least one account")

        if len(self.dataset.merchants) < 1:
            raise ValueError("dataset must contain at least one merchant")

        if len(self.dataset.transactions) < 3:
            raise ValueError("dataset must contain at least three transactions")

        return SyntheticScenarioSet(
            customer_cdc_records=self._build_customer_cdc_records(),
            account_cdc_records=self._build_account_cdc_records(),
            merchant_cdc_records=self._build_merchant_cdc_records(),
            duplicate_transactions=self._build_duplicate_transactions(),
            event_deliveries=self._build_event_deliveries(),
            invalid_transaction_records=(self._build_invalid_transaction_records()),
        )

    def _build_customer_cdc_records(self) -> tuple[Customer, ...]:
        original = self.dataset.customers[0]

        updated = replace(
            original,
            address_line_1="200 Scenario Street",
            city="Sydney",
            state="NSW",
            postcode="2000",
            record_version=2,
            source_updated_at=(original.source_updated_at + timedelta(days=1)),
        )

        deleted = replace(
            updated,
            record_version=3,
            source_updated_at=(updated.source_updated_at + timedelta(days=1)),
            is_deleted=True,
        )

        # Deliberately delivered out of sequence:
        #
        # version 1 -> version 3 -> version 2
        #
        # Later AUTO CDC must use sequence metadata rather than arrival order.
        return (
            original,
            deleted,
            updated,
        )

    def _build_account_cdc_records(self) -> tuple[Account, ...]:
        original = self.dataset.accounts[0]

        blocked = replace(
            original,
            status=AccountStatus.BLOCKED,
            record_version=2,
            source_updated_at=(original.source_updated_at + timedelta(days=1)),
        )

        return (
            original,
            blocked,
        )

    def _build_merchant_cdc_records(self) -> tuple[Merchant, ...]:
        original = self.dataset.merchants[0]

        elevated_risk = replace(
            original,
            risk_rating=RiskRating.HIGH,
            status=MerchantStatus.SUSPENDED,
            record_version=2,
            source_updated_at=(original.source_updated_at + timedelta(days=1)),
        )

        return (
            original,
            elevated_risk,
        )

    def _build_duplicate_transactions(
        self,
    ) -> tuple[PaymentTransaction, ...]:
        transaction = self.dataset.transactions[0]

        # Same business record deliberately delivered twice.
        return (
            transaction,
            transaction,
        )

    def _events_for_transaction(
        self,
        transaction_id: str,
    ) -> tuple[PaymentEvent, ...]:
        events = tuple(
            event
            for event in self.dataset.payment_events
            if event.transaction.transaction_id == transaction_id
        )

        if len(events) != 2:
            raise ValueError("expected exactly two baseline events per transaction")

        return events

    def _build_event_deliveries(
        self,
    ) -> tuple[PaymentEventDelivery, ...]:
        first_transaction = self.dataset.transactions[0]
        second_transaction = self.dataset.transactions[1]
        third_transaction = self.dataset.transactions[2]

        first_events = self._events_for_transaction(first_transaction.transaction_id)
        second_events = self._events_for_transaction(second_transaction.transaction_id)
        third_events = self._events_for_transaction(third_transaction.transaction_id)

        first_authorization = first_events[0]
        first_lifecycle = first_events[1]

        second_authorization = second_events[0]
        second_lifecycle = second_events[1]

        third_authorization = third_events[0]

        out_of_order_base = max(
            second_authorization.event_timestamp,
            second_lifecycle.event_timestamp,
        ) + timedelta(minutes=1)

        return (
            PaymentEventDelivery(
                event=first_authorization,
                arrived_at=(first_authorization.event_timestamp + timedelta(seconds=5)),
                scenario=DeliveryScenario.NORMAL,
            ),
            PaymentEventDelivery(
                event=first_lifecycle,
                arrived_at=(first_lifecycle.event_timestamp + timedelta(seconds=5)),
                scenario=DeliveryScenario.NORMAL,
            ),
            # Same event_id delivered a second time.
            PaymentEventDelivery(
                event=first_authorization,
                arrived_at=(first_authorization.event_timestamp + timedelta(seconds=15)),
                scenario=DeliveryScenario.DUPLICATE,
            ),
            # Sequence 2 deliberately arrives before sequence 1.
            PaymentEventDelivery(
                event=second_lifecycle,
                arrived_at=out_of_order_base,
                scenario=DeliveryScenario.OUT_OF_ORDER,
            ),
            PaymentEventDelivery(
                event=second_authorization,
                arrived_at=(out_of_order_base + timedelta(seconds=30)),
                scenario=DeliveryScenario.OUT_OF_ORDER,
            ),
            # Event time is valid, but ingestion happens much later.
            PaymentEventDelivery(
                event=third_authorization,
                arrived_at=(third_authorization.event_timestamp + timedelta(hours=4)),
                scenario=DeliveryScenario.LATE,
            ),
        )

    def _build_invalid_transaction_records(
        self,
    ) -> tuple[InvalidRawRecord, ...]:
        transaction = self.dataset.transactions[0]

        base_payload: dict[str, object] = {
            "transaction_id": transaction.transaction_id,
            "account_id": transaction.account_id,
            "merchant_id": transaction.merchant_id,
            "event_timestamp": (transaction.event_timestamp.isoformat()),
            "amount": str(transaction.amount),
            "currency": transaction.currency,
            "channel": transaction.channel.value,
            "payment_method": transaction.payment_method.value,
            "status": transaction.status.value,
            "card_present": transaction.card_present,
            "device_id": transaction.device_id,
            "ip_address": transaction.ip_address,
            "country": transaction.country,
        }

        missing_transaction_id = dict(base_payload)
        missing_transaction_id["transaction_id"] = None

        negative_amount = dict(base_payload)
        negative_amount["transaction_id"] = "invalid-negative-amount"
        negative_amount["amount"] = "-50.00"

        invalid_currency = dict(base_payload)
        invalid_currency["transaction_id"] = "invalid-currency"
        invalid_currency["currency"] = "AUDD"

        orphan_account = dict(base_payload)
        orphan_account["transaction_id"] = "invalid-orphan-account"
        orphan_account["account_id"] = "acct-does-not-exist"

        return (
            InvalidRawRecord(
                issue=DataQualityIssue.MISSING_TRANSACTION_ID,
                payload=missing_transaction_id,
            ),
            InvalidRawRecord(
                issue=DataQualityIssue.NEGATIVE_AMOUNT,
                payload=negative_amount,
            ),
            InvalidRawRecord(
                issue=DataQualityIssue.INVALID_CURRENCY,
                payload=invalid_currency,
            ),
            InvalidRawRecord(
                issue=DataQualityIssue.ORPHAN_ACCOUNT,
                payload=orphan_account,
            ),
        )
