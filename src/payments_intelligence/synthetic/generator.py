"""Deterministic synthetic data generator for the payments platform."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from random import Random

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
from payments_intelligence.domain.models import (
    Account,
    Customer,
    FraudCase,
    Merchant,
    PaymentEvent,
    PaymentTransaction,
)
from payments_intelligence.synthetic.config import SyntheticDataConfig

FIRST_NAMES = (
    "Alex",
    "Priya",
    "James",
    "Emma",
    "Daniel",
    "Olivia",
    "Arjun",
    "Sophia",
    "Liam",
    "Mia",
)

LAST_NAMES = (
    "Taylor",
    "Sharma",
    "Wilson",
    "Brown",
    "Singh",
    "Martin",
    "Patel",
    "Thompson",
    "Lee",
    "Anderson",
)

AUSTRALIAN_LOCATIONS = (
    ("Melbourne", "VIC", "3000"),
    ("Sydney", "NSW", "2000"),
    ("Brisbane", "QLD", "4000"),
    ("Adelaide", "SA", "5000"),
    ("Perth", "WA", "6000"),
)

MERCHANT_NAMES = (
    "Metro Grocery",
    "City Electronics",
    "Harbour Restaurant",
    "Cloud Travel",
    "Urban Fashion",
    "Green Pharmacy",
    "Quick Fuel",
    "Digital Marketplace",
    "Central Hotel",
    "Everyday Supplies",
)

MERCHANT_CATEGORY_CODES = (
    "5411",
    "5732",
    "5812",
    "4511",
    "5651",
    "5912",
    "5541",
    "5969",
    "7011",
    "5999",
)

TRANSACTION_COUNTRIES = (
    "AU",
    "AU",
    "AU",
    "AU",
    "AU",
    "AU",
    "AU",
    "SG",
    "US",
    "GB",
)


@dataclass(frozen=True, slots=True)
class SyntheticDataSet:
    """Complete generated synthetic payments dataset."""

    customers: tuple[Customer, ...]
    accounts: tuple[Account, ...]
    merchants: tuple[Merchant, ...]
    transactions: tuple[PaymentTransaction, ...]
    payment_events: tuple[PaymentEvent, ...]
    fraud_cases: tuple[FraudCase, ...]

    def summary(self) -> dict[str, int]:
        """Return record counts for generated entities."""

        return {
            "customers": len(self.customers),
            "accounts": len(self.accounts),
            "merchants": len(self.merchants),
            "transactions": len(self.transactions),
            "payment_events": len(self.payment_events),
            "fraud_cases": len(self.fraud_cases),
        }


class SyntheticDataGenerator:
    """Generate deterministic synthetic payments data."""

    def __init__(self, config: SyntheticDataConfig) -> None:
        self.config = config

    def generate(self) -> SyntheticDataSet:
        """Generate the complete synthetic dataset."""

        rng = Random(self.config.seed)

        customers = self._generate_customers(rng)
        accounts = self._generate_accounts(rng, customers)
        merchants = self._generate_merchants(rng)

        transactions, payment_events, fraud_cases = self._generate_transactions(
            rng,
            accounts,
            merchants,
        )

        return SyntheticDataSet(
            customers=customers,
            accounts=accounts,
            merchants=merchants,
            transactions=transactions,
            payment_events=payment_events,
            fraud_cases=fraud_cases,
        )

    def _generate_customers(
        self,
        rng: Random,
    ) -> tuple[Customer, ...]:
        customers: list[Customer] = []

        for index in range(1, self.config.customer_count + 1):
            first_name = rng.choice(FIRST_NAMES)
            last_name = rng.choice(LAST_NAMES)
            city, state, postcode = rng.choice(AUSTRALIAN_LOCATIONS)

            year = rng.randint(1955, 2003)
            month = rng.randint(1, 12)
            day = rng.randint(1, 28)

            risk_roll = rng.random()

            if risk_roll < 0.70:
                risk_rating = RiskRating.LOW
            elif risk_roll < 0.95:
                risk_rating = RiskRating.MEDIUM
            else:
                risk_rating = RiskRating.HIGH

            customer = Customer(
                customer_id=f"cust-{index:06d}",
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date(year, month, day),
                email=(f"{first_name.lower()}.{last_name.lower()}{index}@example.com"),
                phone=f"+614{index:08d}",
                address_line_1=f"{rng.randint(1, 500)} Example Street",
                city=city,
                state=state,
                postcode=postcode,
                country="AU",
                risk_rating=risk_rating,
                kyc_status=KycStatus.VERIFIED,
                status=CustomerStatus.ACTIVE,
                record_version=1,
                source_updated_at=(self.config.reference_time - timedelta(days=rng.randint(0, 365))),
            )

            customers.append(customer)

        return tuple(customers)

    def _generate_accounts(
        self,
        rng: Random,
        customers: tuple[Customer, ...],
    ) -> tuple[Account, ...]:
        accounts: list[Account] = []

        account_types = tuple(AccountType)

        account_index = 1

        for customer in customers:
            account_count = rng.randint(
                self.config.accounts_per_customer_min,
                self.config.accounts_per_customer_max,
            )

            for _ in range(account_count):
                opened_year = rng.randint(2015, 2025)

                account = Account(
                    account_id=f"acct-{account_index:06d}",
                    customer_id=customer.customer_id,
                    account_type=rng.choice(account_types),
                    currency="AUD",
                    status=AccountStatus.ACTIVE,
                    opened_date=date(
                        opened_year,
                        rng.randint(1, 12),
                        rng.randint(1, 28),
                    ),
                    current_balance=Decimal(f"{rng.uniform(0, 20000):.2f}"),
                    record_version=1,
                    source_updated_at=(self.config.reference_time - timedelta(days=rng.randint(0, 180))),
                )

                accounts.append(account)
                account_index += 1

        return tuple(accounts)

    def _generate_merchants(
        self,
        rng: Random,
    ) -> tuple[Merchant, ...]:
        merchants: list[Merchant] = []

        for index in range(1, self.config.merchant_count + 1):
            merchant_position = (index - 1) % len(MERCHANT_NAMES)

            city, _, _ = rng.choice(AUSTRALIAN_LOCATIONS)

            risk_roll = rng.random()

            if risk_roll < 0.75:
                risk_rating = RiskRating.LOW
            elif risk_roll < 0.95:
                risk_rating = RiskRating.MEDIUM
            else:
                risk_rating = RiskRating.HIGH

            merchant = Merchant(
                merchant_id=f"merchant-{index:06d}",
                merchant_name=(f"{MERCHANT_NAMES[merchant_position]} {index:03d}"),
                merchant_category_code=(MERCHANT_CATEGORY_CODES[merchant_position]),
                city=city,
                country="AU",
                risk_rating=risk_rating,
                status=MerchantStatus.ACTIVE,
                record_version=1,
                source_updated_at=(self.config.reference_time - timedelta(days=rng.randint(0, 365))),
            )

            merchants.append(merchant)

        return tuple(merchants)

    def _generate_transactions(
        self,
        rng: Random,
        accounts: tuple[Account, ...],
        merchants: tuple[Merchant, ...],
    ) -> tuple[
        tuple[PaymentTransaction, ...],
        tuple[PaymentEvent, ...],
        tuple[FraudCase, ...],
    ]:
        transactions: list[PaymentTransaction] = []
        payment_events: list[PaymentEvent] = []
        fraud_cases: list[FraudCase] = []

        channels = tuple(PaymentChannel)
        payment_methods = tuple(PaymentMethod)

        event_index = 1
        fraud_case_index = 1

        for transaction_index in range(
            1,
            self.config.transaction_count + 1,
        ):
            account = rng.choice(accounts)
            merchant = rng.choice(merchants)

            suspicious = rng.random() < self.config.suspicious_transaction_rate

            declined = rng.random() < 0.08

            transaction_status = TransactionStatus.DECLINED if declined else TransactionStatus.SETTLED

            raw_amount = min(
                rng.expovariate(1 / 120) + 5,
                2000,
            )

            if suspicious:
                raw_amount = min(
                    raw_amount * rng.uniform(3, 7) + 250,
                    5000,
                )

            amount = Decimal(f"{raw_amount:.2f}")

            if suspicious:
                country = rng.choice(("SG", "US", "GB"))
            else:
                country = rng.choice(TRANSACTION_COUNTRIES)

            channel = rng.choice(channels)
            payment_method = rng.choice(payment_methods)

            event_timestamp = self.config.reference_time - timedelta(
                seconds=rng.randint(
                    0,
                    30 * 24 * 60 * 60,
                )
            )

            transaction = PaymentTransaction(
                transaction_id=f"txn-{transaction_index:08d}",
                account_id=account.account_id,
                merchant_id=merchant.merchant_id,
                event_timestamp=event_timestamp,
                amount=amount,
                currency="AUD",
                channel=channel,
                payment_method=payment_method,
                status=transaction_status,
                card_present=channel is PaymentChannel.POS,
                device_id=(None if channel is PaymentChannel.ATM else f"device-{rng.randint(1, 250):04d}"),
                ip_address=(
                    None
                    if channel in (PaymentChannel.POS, PaymentChannel.ATM)
                    else (f"203.0.{rng.randint(0, 255)}.{rng.randint(1, 254)}")
                ),
                country=country,
            )

            transactions.append(transaction)

            authorization_event = PaymentEvent(
                event_id=f"event-{event_index:09d}",
                event_type=PaymentEventType.AUTHORIZATION,
                event_timestamp=transaction.event_timestamp,
                sequence_number=1,
                transaction=transaction,
            )

            event_index += 1
            payment_events.append(authorization_event)

            if declined:
                lifecycle_event_type = PaymentEventType.DECLINE
            else:
                lifecycle_event_type = PaymentEventType.SETTLEMENT

            lifecycle_event = PaymentEvent(
                event_id=f"event-{event_index:09d}",
                event_type=lifecycle_event_type,
                event_timestamp=(transaction.event_timestamp + timedelta(seconds=rng.randint(1, 120))),
                sequence_number=2,
                transaction=transaction,
            )

            event_index += 1
            payment_events.append(lifecycle_event)

            if suspicious and not declined:
                fraud_case = self._generate_fraud_case(
                    rng=rng,
                    transaction=transaction,
                    case_index=fraud_case_index,
                )

                fraud_cases.append(fraud_case)
                fraud_case_index += 1

        return (
            tuple(transactions),
            tuple(payment_events),
            tuple(fraud_cases),
        )

    def _generate_fraud_case(
        self,
        rng: Random,
        transaction: PaymentTransaction,
        case_index: int,
    ) -> FraudCase:
        opened_at = transaction.event_timestamp + timedelta(minutes=rng.randint(5, 180))

        outcome_roll = rng.random()

        if outcome_roll < 0.60:
            outcome = FraudOutcome.CONFIRMED_FRAUD
            status = FraudCaseStatus.CLOSED
            analyst_notes = "Customer confirmed the payment was unauthorized."
        elif outcome_roll < 0.95:
            outcome = FraudOutcome.LEGITIMATE
            status = FraudCaseStatus.CLOSED
            analyst_notes = "Customer confirmed the transaction was legitimate."
        else:
            outcome = FraudOutcome.UNDETERMINED
            status = FraudCaseStatus.INVESTIGATING
            analyst_notes = "Investigation remains open pending customer verification."

        closed_at = opened_at + timedelta(minutes=rng.randint(15, 240)) if status is FraudCaseStatus.CLOSED else None

        return FraudCase(
            case_id=f"case-{case_index:06d}",
            transaction_id=transaction.transaction_id,
            opened_at=opened_at,
            status=status,
            suspected_reason=("High-value payment with unusual geography or behaviour"),
            outcome=outcome,
            analyst_notes=analyst_notes,
            closed_at=closed_at,
        )
