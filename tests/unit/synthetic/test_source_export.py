"""Tests for local source-system dataset exports."""

import csv
import json
from pathlib import Path

from payments_intelligence.synthetic import (
    DeliveryScenario,
    LocalSourceDatasetExporter,
    LocalSourceExportConfig,
    SyntheticDataConfig,
)


def export_small_dataset(
    output_root: Path,
):
    config = LocalSourceExportConfig(
        output_root=output_root,
        synthetic=SyntheticDataConfig(
            seed=42,
            customer_count=10,
            merchant_count=5,
            transaction_count=50,
            suspicious_transaction_rate=0.10,
        ),
    )

    return LocalSourceDatasetExporter(config).export()


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_manifest_files_exist(tmp_path: Path) -> None:
    manifest = export_small_dataset(tmp_path)

    for relative_path in manifest.files:
        assert (manifest.root / relative_path).exists()


def test_postgres_customer_snapshot_has_expected_rows(
    tmp_path: Path,
) -> None:
    manifest = export_small_dataset(tmp_path)

    path = manifest.root / "postgres" / "snapshots" / "customers.csv"

    with path.open(
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 10


def test_postgres_customer_cdc_preserves_delivery_order(
    tmp_path: Path,
) -> None:
    manifest = export_small_dataset(tmp_path)

    path = manifest.root / "postgres" / "cdc" / "customers.csv"

    with path.open(
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    versions = [int(row["record_version"]) for row in rows]

    assert versions == [1, 3, 2]


def test_s3_clean_transactions_are_partitioned_by_date(
    tmp_path: Path,
) -> None:
    manifest = export_small_dataset(tmp_path)

    clean_root = manifest.root / "s3" / "historical_transactions" / "clean"

    files = sorted(clean_root.glob("event_date=*/transactions.jsonl"))

    assert files

    total_records = sum(len(read_jsonl(path)) for path in files)

    assert total_records == 50


def test_s3_duplicate_scenario_contains_same_transaction_twice(
    tmp_path: Path,
) -> None:
    manifest = export_small_dataset(tmp_path)

    path = manifest.root / "s3" / "historical_transactions" / "scenarios" / "duplicates" / "transactions.jsonl"

    records = read_jsonl(path)

    assert len(records) == 2

    assert records[0]["transaction_id"] == records[1]["transaction_id"]


def test_s3_invalid_scenarios_are_exported(
    tmp_path: Path,
) -> None:
    manifest = export_small_dataset(tmp_path)

    path = manifest.root / "s3" / "historical_transactions" / "scenarios" / "invalid" / "transactions.jsonl"

    records = read_jsonl(path)

    issues = {record["issue"] for record in records}

    assert issues == {
        "MISSING_TRANSACTION_ID",
        "NEGATIVE_AMOUNT",
        "INVALID_CURRENCY",
        "ORPHAN_ACCOUNT",
    }


def test_kafka_clean_stream_contains_two_events_per_transaction(
    tmp_path: Path,
) -> None:
    manifest = export_small_dataset(tmp_path)

    path = manifest.root / "kafka" / "payment_events" / "clean.jsonl"

    records = read_jsonl(path)

    assert len(records) == 100


def test_kafka_scenario_stream_contains_expected_behaviours(
    tmp_path: Path,
) -> None:
    manifest = export_small_dataset(tmp_path)

    path = manifest.root / "kafka" / "payment_events" / "scenarios.jsonl"

    records = read_jsonl(path)

    scenarios = {record["scenario"] for record in records}

    assert DeliveryScenario.NORMAL.value in scenarios
    assert DeliveryScenario.DUPLICATE.value in scenarios
    assert DeliveryScenario.OUT_OF_ORDER.value in scenarios
    assert DeliveryScenario.LATE.value in scenarios


def test_export_is_deterministic(
    tmp_path: Path,
) -> None:
    first = export_small_dataset(tmp_path / "first")

    second = export_small_dataset(tmp_path / "second")

    assert first.files == second.files
    assert first.counts == second.counts

    for relative_path in first.files:
        first_contents = (first.root / relative_path).read_bytes()

        second_contents = (second.root / relative_path).read_bytes()

        assert first_contents == second_contents
