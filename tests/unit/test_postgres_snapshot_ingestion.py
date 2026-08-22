"""Tests for Milestone 3D PostgreSQL snapshot batch ingestion."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_postgres_external_volume_exists() -> None:
    """PostgreSQL source extracts must have a governed external volume."""

    path = ROOT / "bundle" / "resources" / "postgres_batch_volume.yml"

    assert path.exists()


def test_postgres_volume_is_external() -> None:
    """PostgreSQL source storage must remain customer-owned S3 storage."""

    path = ROOT / "bundle" / "resources" / "postgres_batch_volume.yml"

    with path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    volume = config["resources"]["volumes"]["postgres_batch_source_volume"]

    assert volume["name"] == "postgres_batch_source"
    assert volume["volume_type"] == "EXTERNAL"


def test_postgres_volume_uses_postgres_root() -> None:
    """The external volume should support snapshots and future CDC extracts."""

    path = ROOT / "bundle" / "resources" / "postgres_batch_volume.yml"

    with path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    volume = config["resources"]["volumes"]["postgres_batch_source_volume"]

    assert volume["storage_location"] == "${var.s3_landing_url}/postgres"


def test_postgres_snapshot_sql_exists() -> None:
    """The PostgreSQL snapshot ingestion SQL must exist."""

    path = ROOT / "sql" / "ingestion" / "03d_postgres_snapshot_ingestion.sql"

    assert path.exists()


def test_snapshot_sql_creates_all_expected_tables() -> None:
    """All PostgreSQL snapshot entities should have raw Delta tables."""

    path = ROOT / "sql" / "ingestion" / "03d_postgres_snapshot_ingestion.sql"

    sql = path.read_text(encoding="utf-8")

    expected_tables = (
        "customers_snapshot",
        "accounts_snapshot",
        "merchants_snapshot",
        "fraud_cases_snapshot",
    )

    for table in expected_tables:
        assert table in sql


def test_snapshot_sql_uses_copy_into() -> None:
    """Each snapshot entity must use retry-safe COPY INTO ingestion."""

    path = ROOT / "sql" / "ingestion" / "03d_postgres_snapshot_ingestion.sql"

    sql = path.read_text(encoding="utf-8").upper()

    assert sql.count("COPY INTO") >= 4


def test_snapshot_copy_into_does_not_force_reload() -> None:
    """Snapshot ingestion must preserve COPY INTO idempotency."""

    path = ROOT / "sql" / "ingestion" / "03d_postgres_snapshot_ingestion.sql"

    sql = path.read_text(encoding="utf-8").upper()

    assert "FORCE = TRUE" not in sql
    assert "FORCE=TRUE" not in sql


def test_snapshot_sql_uses_csv_headers() -> None:
    """PostgreSQL extract files contain named CSV headers."""

    path = ROOT / "sql" / "ingestion" / "03d_postgres_snapshot_ingestion.sql"

    sql = path.read_text(encoding="utf-8").lower()

    assert sql.count("'header' = 'true'") >= 4


def test_snapshot_ingestion_captures_lineage() -> None:
    """All raw snapshot tables must retain physical source lineage."""

    path = ROOT / "sql" / "ingestion" / "03d_postgres_snapshot_ingestion.sql"

    sql = path.read_text(encoding="utf-8")

    assert "_metadata.file_path" in sql
    assert "_metadata.file_name" in sql
    assert "ingested_at" in sql


def test_postgres_reconciliation_sql_exists() -> None:
    """Step 3D must include source-to-target reconciliation."""

    path = ROOT / "sql" / "ingestion" / "03d_reconcile_postgres_snapshots.sql"

    assert path.exists()


def test_reconciliation_validates_account_customer_relationship() -> None:
    """Accounts must resolve to valid customers."""

    path = ROOT / "sql" / "ingestion" / "03d_reconcile_postgres_snapshots.sql"

    sql = path.read_text(encoding="utf-8")

    assert "accounts_without_customer" in sql


def test_reconciliation_validates_transaction_account_relationship() -> None:
    """Transactions must resolve to valid accounts."""

    path = ROOT / "sql" / "ingestion" / "03d_reconcile_postgres_snapshots.sql"

    sql = path.read_text(encoding="utf-8")

    assert "transactions_without_account" in sql


def test_reconciliation_validates_transaction_merchant_relationship() -> None:
    """Transactions must resolve to valid merchants."""

    path = ROOT / "sql" / "ingestion" / "03d_reconcile_postgres_snapshots.sql"

    sql = path.read_text(encoding="utf-8")

    assert "transactions_without_merchant" in sql


def test_reconciliation_validates_fraud_transaction_relationship() -> None:
    """Every fraud case must resolve to an ingested transaction."""

    path = ROOT / "sql" / "ingestion" / "03d_reconcile_postgres_snapshots.sql"

    sql = path.read_text(encoding="utf-8")

    assert "fraud_cases_without_transaction" in sql
