"""Configuration for deterministic synthetic payments data generation."""

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class SyntheticDataConfig:
    """Controls the size and repeatability of generated synthetic data."""

    seed: int = 42

    customer_count: int = 100
    accounts_per_customer_min: int = 1
    accounts_per_customer_max: int = 3
    merchant_count: int = 40
    transaction_count: int = 1000

    suspicious_transaction_rate: float = 0.05

    reference_time: datetime = datetime(
        2026,
        8,
        1,
        0,
        0,
        tzinfo=UTC,
    )

    def __post_init__(self) -> None:
        if self.customer_count < 1:
            raise ValueError("customer_count must be greater than zero")

        if self.accounts_per_customer_min < 1:
            raise ValueError("accounts_per_customer_min must be greater than zero")

        if self.accounts_per_customer_max < self.accounts_per_customer_min:
            raise ValueError("accounts_per_customer_max must be greater than or equal to accounts_per_customer_min")

        if self.merchant_count < 1:
            raise ValueError("merchant_count must be greater than zero")

        if self.transaction_count < 1:
            raise ValueError("transaction_count must be greater than zero")

        if not 0 <= self.suspicious_transaction_rate <= 1:
            raise ValueError("suspicious_transaction_rate must be between 0 and 1")

        if self.reference_time.tzinfo is None or self.reference_time.utcoffset() is None:
            raise ValueError("reference_time must be timezone-aware")
