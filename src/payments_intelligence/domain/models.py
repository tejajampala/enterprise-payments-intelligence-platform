"""Canonical domain models for the Enterprise Payments Intelligence Platform."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from payments_intelligence.domain.enums import (
    AccountStatus,
    AccountType,
    CustomerStatus,
    FraudCaseStatus,
    FraudOutcome,
    KycStatus,
    MerchantStatus,
    PaymentChannel,
    PaymentEventType,
    PaymentMethod,
    RiskRating,
    TransactionStatus,
)


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_positive_decimal(value: Decimal, field_name: str) -> None:
    if value <= Decimal("0"):
        raise ValueError(f"{field_name} must be greater than zero")


def _require_non_negative_decimal(value: Decimal, field_name: str) -> None:
    if value < Decimal("0"):
        raise ValueError(f"{field_name} must not be negative")


def _validate_currency(currency: str) -> None:
    if len(currency) != 3 or not currency.isalpha() or currency.upper() != currency:
        raise ValueError("currency must be a three-letter uppercase ISO currency code")


def _validate_country(country: str) -> None:
    if len(country) != 2 or not country.isalpha() or country.upper() != country:
        raise ValueError("country must be a two-letter uppercase ISO country code")


@dataclass(frozen=True, slots=True)
class Customer:
    """Canonical customer master-data record."""

    customer_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    email: str
    phone: str
    address_line_1: str
    city: str
    state: str
    postcode: str
    country: str
    risk_rating: RiskRating
    kyc_status: KycStatus
    status: CustomerStatus
    record_version: int
    source_updated_at: datetime
    is_deleted: bool = False

    def __post_init__(self) -> None:
        _require_non_empty(self.customer_id, "customer_id")
        _require_non_empty(self.first_name, "first_name")
        _require_non_empty(self.last_name, "last_name")
        _require_non_empty(self.email, "email")
        _validate_country(self.country)
        _require_timezone_aware(self.source_updated_at, "source_updated_at")

        if self.record_version < 1:
            raise ValueError("record_version must be greater than or equal to 1")


@dataclass(frozen=True, slots=True)
class Account:
    """Canonical customer account record."""

    account_id: str
    customer_id: str
    account_type: AccountType
    currency: str
    status: AccountStatus
    opened_date: date
    current_balance: Decimal
    record_version: int
    source_updated_at: datetime
    is_deleted: bool = False

    def __post_init__(self) -> None:
        _require_non_empty(self.account_id, "account_id")
        _require_non_empty(self.customer_id, "customer_id")
        _validate_currency(self.currency)
        _require_non_negative_decimal(self.current_balance, "current_balance")
        _require_timezone_aware(self.source_updated_at, "source_updated_at")

        if self.record_version < 1:
            raise ValueError("record_version must be greater than or equal to 1")


@dataclass(frozen=True, slots=True)
class Merchant:
    """Canonical merchant master-data record."""

    merchant_id: str
    merchant_name: str
    merchant_category_code: str
    city: str
    country: str
    risk_rating: RiskRating
    status: MerchantStatus
    record_version: int
    source_updated_at: datetime
    is_deleted: bool = False

    def __post_init__(self) -> None:
        _require_non_empty(self.merchant_id, "merchant_id")
        _require_non_empty(self.merchant_name, "merchant_name")
        _validate_country(self.country)
        _require_timezone_aware(self.source_updated_at, "source_updated_at")

        if len(self.merchant_category_code) != 4 or not self.merchant_category_code.isdigit():
            raise ValueError("merchant_category_code must contain four digits")

        if self.record_version < 1:
            raise ValueError("record_version must be greater than or equal to 1")


@dataclass(frozen=True, slots=True)
class PaymentTransaction:
    """Canonical payment transaction."""

    transaction_id: str
    account_id: str
    merchant_id: str
    event_timestamp: datetime
    amount: Decimal
    currency: str
    channel: PaymentChannel
    payment_method: PaymentMethod
    status: TransactionStatus
    card_present: bool
    device_id: str | None
    ip_address: str | None
    country: str

    def __post_init__(self) -> None:
        _require_non_empty(self.transaction_id, "transaction_id")
        _require_non_empty(self.account_id, "account_id")
        _require_non_empty(self.merchant_id, "merchant_id")
        _require_timezone_aware(self.event_timestamp, "event_timestamp")
        _require_positive_decimal(self.amount, "amount")
        _validate_currency(self.currency)
        _validate_country(self.country)


@dataclass(frozen=True, slots=True)
class PaymentEvent:
    """Streaming envelope for transaction lifecycle events."""

    event_id: str
    event_type: PaymentEventType
    event_timestamp: datetime
    sequence_number: int
    transaction: PaymentTransaction

    def __post_init__(self) -> None:
        _require_non_empty(self.event_id, "event_id")
        _require_timezone_aware(self.event_timestamp, "event_timestamp")

        if self.sequence_number < 1:
            raise ValueError("sequence_number must be greater than or equal to 1")


@dataclass(frozen=True, slots=True)
class FraudCase:
    """Fraud investigation record linked to a payment transaction."""

    case_id: str
    transaction_id: str
    opened_at: datetime
    status: FraudCaseStatus
    suspected_reason: str
    outcome: FraudOutcome
    analyst_notes: str | None = None
    closed_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.case_id, "case_id")
        _require_non_empty(self.transaction_id, "transaction_id")
        _require_non_empty(self.suspected_reason, "suspected_reason")
        _require_timezone_aware(self.opened_at, "opened_at")

        if self.closed_at is not None:
            _require_timezone_aware(self.closed_at, "closed_at")

            if self.closed_at < self.opened_at:
                raise ValueError("closed_at must not be before opened_at")
