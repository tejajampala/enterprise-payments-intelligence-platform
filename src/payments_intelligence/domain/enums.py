"""Enumerations used by the enterprise payments domain."""

from enum import StrEnum


class RiskRating(StrEnum):
    """Customer or merchant risk classification."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class KycStatus(StrEnum):
    """Know Your Customer verification status."""

    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class CustomerStatus(StrEnum):
    """Customer lifecycle status."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class AccountType(StrEnum):
    """Supported payment account types."""

    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"
    CREDIT_CARD = "CREDIT_CARD"


class AccountStatus(StrEnum):
    """Account lifecycle status."""

    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    CLOSED = "CLOSED"


class MerchantStatus(StrEnum):
    """Merchant lifecycle status."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class PaymentChannel(StrEnum):
    """Channel through which a payment originates."""

    POS = "POS"
    ECOMMERCE = "ECOMMERCE"
    MOBILE = "MOBILE"
    ATM = "ATM"


class PaymentMethod(StrEnum):
    """Payment instrument or method."""

    DEBIT_CARD = "DEBIT_CARD"
    CREDIT_CARD = "CREDIT_CARD"
    DIGITAL_WALLET = "DIGITAL_WALLET"
    BANK_TRANSFER = "BANK_TRANSFER"


class TransactionStatus(StrEnum):
    """Current transaction processing status."""

    AUTHORIZED = "AUTHORIZED"
    DECLINED = "DECLINED"
    SETTLED = "SETTLED"
    REVERSED = "REVERSED"
    REFUNDED = "REFUNDED"


class PaymentEventType(StrEnum):
    """Streaming payment lifecycle event."""

    AUTHORIZATION = "AUTHORIZATION"
    DECLINE = "DECLINE"
    SETTLEMENT = "SETTLEMENT"
    REVERSAL = "REVERSAL"
    REFUND = "REFUND"


class FraudCaseStatus(StrEnum):
    """Fraud investigation case status."""

    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    CLOSED = "CLOSED"


class FraudOutcome(StrEnum):
    """Final fraud investigation outcome."""

    CONFIRMED_FRAUD = "CONFIRMED_FRAUD"
    LEGITIMATE = "LEGITIMATE"
    UNDETERMINED = "UNDETERMINED"
