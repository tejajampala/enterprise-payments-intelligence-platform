"""Export deterministic synthetic data into local source-system datasets."""

import csv
import json
import shutil
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from payments_intelligence.domain.models import (
    Account,
    Customer,
    FraudCase,
    Merchant,
    PaymentEvent,
    PaymentTransaction,
)
from payments_intelligence.synthetic.config import SyntheticDataConfig
from payments_intelligence.synthetic.generator import (
    SyntheticDataGenerator,
    SyntheticDataSet,
)
from payments_intelligence.synthetic.scenarios import (
    DeliveryScenario,
    SyntheticScenarioBuilder,
    SyntheticScenarioSet,
)

CUSTOMER_FIELDS = (
    "customer_id",
    "first_name",
    "last_name",
    "date_of_birth",
    "email",
    "phone",
    "address_line_1",
    "city",
    "state",
    "postcode",
    "country",
    "risk_rating",
    "kyc_status",
    "status",
    "record_version",
    "source_updated_at",
    "is_deleted",
)

ACCOUNT_FIELDS = (
    "account_id",
    "customer_id",
    "account_type",
    "currency",
    "status",
    "opened_date",
    "current_balance",
    "record_version",
    "source_updated_at",
    "is_deleted",
)

MERCHANT_FIELDS = (
    "merchant_id",
    "merchant_name",
    "merchant_category_code",
    "city",
    "country",
    "risk_rating",
    "status",
    "record_version",
    "source_updated_at",
    "is_deleted",
)

FRAUD_CASE_FIELDS = (
    "case_id",
    "transaction_id",
    "opened_at",
    "status",
    "suspected_reason",
    "outcome",
    "analyst_notes",
    "closed_at",
)


@dataclass(frozen=True, slots=True)
class LocalSourceExportConfig:
    """Configuration for local source-system dataset export."""

    output_root: Path = Path("data/generated/source_systems")
    kafka_topic: str = "payments.events.v1"

    synthetic: SyntheticDataConfig = field(default_factory=SyntheticDataConfig)

    def __post_init__(self) -> None:
        if not self.kafka_topic.strip():
            raise ValueError("kafka_topic must not be empty")


@dataclass(frozen=True, slots=True)
class SourceDatasetManifest:
    """Metadata describing one exported synthetic source-system dataset."""

    root: Path
    synthetic_seed: int
    files: tuple[str, ...]
    counts: dict[str, int]


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _datetime_text(value: datetime | None) -> str:
    if value is None:
        return ""

    return value.isoformat()


def _customer_row(customer: Customer) -> dict[str, str]:
    return {
        "customer_id": customer.customer_id,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "date_of_birth": customer.date_of_birth.isoformat(),
        "email": customer.email,
        "phone": customer.phone,
        "address_line_1": customer.address_line_1,
        "city": customer.city,
        "state": customer.state,
        "postcode": customer.postcode,
        "country": customer.country,
        "risk_rating": customer.risk_rating.value,
        "kyc_status": customer.kyc_status.value,
        "status": customer.status.value,
        "record_version": str(customer.record_version),
        "source_updated_at": customer.source_updated_at.isoformat(),
        "is_deleted": _bool_text(customer.is_deleted),
    }


def _account_row(account: Account) -> dict[str, str]:
    return {
        "account_id": account.account_id,
        "customer_id": account.customer_id,
        "account_type": account.account_type.value,
        "currency": account.currency,
        "status": account.status.value,
        "opened_date": account.opened_date.isoformat(),
        "current_balance": str(account.current_balance),
        "record_version": str(account.record_version),
        "source_updated_at": account.source_updated_at.isoformat(),
        "is_deleted": _bool_text(account.is_deleted),
    }


def _merchant_row(merchant: Merchant) -> dict[str, str]:
    return {
        "merchant_id": merchant.merchant_id,
        "merchant_name": merchant.merchant_name,
        "merchant_category_code": merchant.merchant_category_code,
        "city": merchant.city,
        "country": merchant.country,
        "risk_rating": merchant.risk_rating.value,
        "status": merchant.status.value,
        "record_version": str(merchant.record_version),
        "source_updated_at": merchant.source_updated_at.isoformat(),
        "is_deleted": _bool_text(merchant.is_deleted),
    }


def _fraud_case_row(fraud_case: FraudCase) -> dict[str, str]:
    return {
        "case_id": fraud_case.case_id,
        "transaction_id": fraud_case.transaction_id,
        "opened_at": fraud_case.opened_at.isoformat(),
        "status": fraud_case.status.value,
        "suspected_reason": fraud_case.suspected_reason,
        "outcome": fraud_case.outcome.value,
        "analyst_notes": fraud_case.analyst_notes or "",
        "closed_at": _datetime_text(fraud_case.closed_at),
    }


def _transaction_payload(
    transaction: PaymentTransaction,
) -> dict[str, object]:
    return {
        "transaction_id": transaction.transaction_id,
        "account_id": transaction.account_id,
        "merchant_id": transaction.merchant_id,
        "event_timestamp": transaction.event_timestamp.isoformat(),
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


def _event_payload(event: PaymentEvent) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "event_timestamp": event.event_timestamp.isoformat(),
        "sequence_number": event.sequence_number,
        "transaction": _transaction_payload(event.transaction),
    }


def _kafka_envelope(
    event: PaymentEvent,
    arrived_at: datetime,
    scenario: DeliveryScenario,
    topic: str,
) -> dict[str, object]:
    return {
        "topic": topic,
        "message_key": event.transaction.transaction_id,
        "simulated_arrival_at": arrived_at.isoformat(),
        "scenario": scenario.value,
        "payload": _event_payload(event),
    }


def _write_csv(
    path: Path,
    fieldnames: tuple[str, ...],
    rows: Iterable[dict[str, str]],
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)

    count = 0

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(fieldnames),
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(row)
            count += 1

    return count


def _write_jsonl(
    path: Path,
    records: Iterable[dict[str, object]],
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)

    count = 0

    with path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:
        for record in records:
            file.write(
                json.dumps(
                    record,
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )
            file.write("\n")
            count += 1

    return count


class LocalSourceDatasetExporter:
    """Export synthetic data into local representations of source systems."""

    def __init__(self, config: LocalSourceExportConfig) -> None:
        self.config = config

    def export(self) -> SourceDatasetManifest:
        """Generate and export all local source-system datasets."""

        dataset = SyntheticDataGenerator(self.config.synthetic).generate()

        scenarios = SyntheticScenarioBuilder(dataset).build()

        run_root = self.config.output_root / f"seed-{self.config.synthetic.seed}"

        if run_root.exists():
            shutil.rmtree(run_root)

        run_root.mkdir(parents=True, exist_ok=True)

        counts: dict[str, int] = {}
        files: list[str] = []

        self._write_postgres(
            run_root,
            dataset,
            scenarios,
            counts,
            files,
        )

        self._write_s3(
            run_root,
            dataset,
            scenarios,
            counts,
            files,
        )

        self._write_kafka(
            run_root,
            dataset,
            scenarios,
            counts,
            files,
        )

        files.append("manifest.json")

        manifest_payload: dict[str, object] = {
            "synthetic_seed": self.config.synthetic.seed,
            "reference_time": (self.config.synthetic.reference_time.isoformat()),
            "kafka_topic": self.config.kafka_topic,
            "counts": counts,
            "files": sorted(files),
        }

        manifest_path = run_root / "manifest.json"

        manifest_path.write_text(
            json.dumps(
                manifest_payload,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        return SourceDatasetManifest(
            root=run_root,
            synthetic_seed=self.config.synthetic.seed,
            files=tuple(sorted(files)),
            counts=counts,
        )

    def _write_postgres(
        self,
        run_root: Path,
        dataset: SyntheticDataSet,
        scenarios: SyntheticScenarioSet,
        counts: dict[str, int],
        files: list[str],
    ) -> None:
        snapshot_root = run_root / "postgres" / "snapshots"
        cdc_root = run_root / "postgres" / "cdc"

        exports = (
            (
                snapshot_root / "customers.csv",
                CUSTOMER_FIELDS,
                (_customer_row(customer) for customer in dataset.customers),
                "postgres_customer_snapshot",
            ),
            (
                snapshot_root / "accounts.csv",
                ACCOUNT_FIELDS,
                (_account_row(account) for account in dataset.accounts),
                "postgres_account_snapshot",
            ),
            (
                snapshot_root / "merchants.csv",
                MERCHANT_FIELDS,
                (_merchant_row(merchant) for merchant in dataset.merchants),
                "postgres_merchant_snapshot",
            ),
            (
                snapshot_root / "fraud_cases.csv",
                FRAUD_CASE_FIELDS,
                (_fraud_case_row(fraud_case) for fraud_case in dataset.fraud_cases),
                "postgres_fraud_case_snapshot",
            ),
            (
                cdc_root / "customers.csv",
                CUSTOMER_FIELDS,
                (_customer_row(customer) for customer in scenarios.customer_cdc_records),
                "postgres_customer_cdc",
            ),
            (
                cdc_root / "accounts.csv",
                ACCOUNT_FIELDS,
                (_account_row(account) for account in scenarios.account_cdc_records),
                "postgres_account_cdc",
            ),
            (
                cdc_root / "merchants.csv",
                MERCHANT_FIELDS,
                (_merchant_row(merchant) for merchant in scenarios.merchant_cdc_records),
                "postgres_merchant_cdc",
            ),
        )

        for path, fieldnames, rows, count_name in exports:
            counts[count_name] = _write_csv(
                path,
                fieldnames,
                rows,
            )

            files.append(path.relative_to(run_root).as_posix())

    def _write_s3(
        self,
        run_root: Path,
        dataset: SyntheticDataSet,
        scenarios: SyntheticScenarioSet,
        counts: dict[str, int],
        files: list[str],
    ) -> None:
        clean_root = run_root / "s3" / "historical_transactions" / "clean"

        transactions_by_date: dict[
            str,
            list[PaymentTransaction],
        ] = defaultdict(list)

        for transaction in dataset.transactions:
            event_date = transaction.event_timestamp.date().isoformat()

            transactions_by_date[event_date].append(transaction)

        clean_transaction_count = 0

        for event_date in sorted(transactions_by_date):
            transactions = sorted(
                transactions_by_date[event_date],
                key=lambda transaction: transaction.transaction_id,
            )

            path = clean_root / f"event_date={event_date}" / "transactions.jsonl"

            count = _write_jsonl(
                path,
                (_transaction_payload(transaction) for transaction in transactions),
            )

            clean_transaction_count += count

            files.append(path.relative_to(run_root).as_posix())

        counts["s3_clean_transactions"] = clean_transaction_count

        counts["s3_clean_partitions"] = len(transactions_by_date)

        duplicate_path = (
            run_root
            / "s3"
            / "historical_transactions"
            / "scenarios"
            / "duplicates"
            / "transactions.jsonl"
        )

        counts["s3_duplicate_transactions"] = _write_jsonl(
            duplicate_path,
            (_transaction_payload(transaction) for transaction in scenarios.duplicate_transactions),
        )

        files.append(duplicate_path.relative_to(run_root).as_posix())

        invalid_path = (
            run_root
            / "s3"
            / "historical_transactions"
            / "scenarios"
            / "invalid"
            / "transactions.jsonl"
        )

        counts["s3_invalid_transactions"] = _write_jsonl(
            invalid_path,
            (
                {
                    "issue": record.issue.value,
                    "payload": record.payload,
                }
                for record in scenarios.invalid_transaction_records
            ),
        )

        files.append(invalid_path.relative_to(run_root).as_posix())

    def _write_kafka(
        self,
        run_root: Path,
        dataset: SyntheticDataSet,
        scenarios: SyntheticScenarioSet,
        counts: dict[str, int],
        files: list[str],
    ) -> None:
        kafka_root = run_root / "kafka" / "payment_events"

        clean_path = kafka_root / "clean.jsonl"

        counts["kafka_clean_events"] = _write_jsonl(
            clean_path,
            (
                _kafka_envelope(
                    event=event,
                    arrived_at=(event.event_timestamp + timedelta(seconds=5)),
                    scenario=DeliveryScenario.NORMAL,
                    topic=self.config.kafka_topic,
                )
                for event in dataset.payment_events
            ),
        )

        files.append(clean_path.relative_to(run_root).as_posix())

        scenario_path = kafka_root / "scenarios.jsonl"

        counts["kafka_scenario_deliveries"] = _write_jsonl(
            scenario_path,
            (
                _kafka_envelope(
                    event=delivery.event,
                    arrived_at=delivery.arrived_at,
                    scenario=delivery.scenario,
                    topic=self.config.kafka_topic,
                )
                for delivery in scenarios.event_deliveries
            ),
        )

        files.append(scenario_path.relative_to(run_root).as_posix())
