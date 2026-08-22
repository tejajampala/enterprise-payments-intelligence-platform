"""Tests for Milestone 3C production-style S3 batch ingestion."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_s3_external_volume_resource_exists() -> None:
    """The S3-backed external volume configuration must exist."""

    path = ROOT / "bundle" / "resources" / "s3_batch_volume.yml"

    assert path.exists()


def test_s3_batch_volume_is_external() -> None:
    """Historical transaction storage must use an external UC volume."""

    path = ROOT / "bundle" / "resources" / "s3_batch_volume.yml"

    with path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    volume = config["resources"]["volumes"]["s3_batch_source_volume"]

    assert volume["name"] == "s3_batch_source"
    assert volume["volume_type"] == "EXTERNAL"


def test_s3_batch_volume_uses_existing_catalog() -> None:
    """The external volume should use the existing payments catalog."""

    path = ROOT / "bundle" / "resources" / "s3_batch_volume.yml"

    with path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    volume = config["resources"]["volumes"]["s3_batch_source_volume"]

    assert volume["catalog_name"] == "${var.catalog_name}"


def test_s3_batch_volume_uses_landing_schema() -> None:
    """The external volume must reside in the governed landing schema."""

    path = ROOT / "bundle" / "resources" / "s3_batch_volume.yml"

    with path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    volume = config["resources"]["volumes"]["s3_batch_source_volume"]

    assert volume["schema_name"] == "${resources.schemas.landing_schema.name}"


def test_s3_batch_volume_uses_external_location_path() -> None:
    """The external volume must be underneath the governed S3 landing root."""

    path = ROOT / "bundle" / "resources" / "s3_batch_volume.yml"

    with path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    volume = config["resources"]["volumes"]["s3_batch_source_volume"]

    assert volume["storage_location"] == "${var.s3_landing_url}/historical_transactions"


def test_s3_copy_into_sql_exists() -> None:
    """The production S3 COPY INTO SQL file must exist."""

    path = ROOT / "sql" / "ingestion" / "03c_payment_transactions_s3.sql"

    assert path.exists()


def test_s3_copy_into_targets_expected_table() -> None:
    """COPY INTO must target the Step 3C S3 ingestion table."""

    path = ROOT / "sql" / "ingestion" / "03c_payment_transactions_s3.sql"

    sql = path.read_text(encoding="utf-8")

    assert "payments_dev.ingestion.payment_transactions_batch_s3" in sql


def test_s3_copy_into_reads_external_volume() -> None:
    """COPY INTO must use the governed external-volume path."""

    path = ROOT / "sql" / "ingestion" / "03c_payment_transactions_s3.sql"

    sql = path.read_text(encoding="utf-8")

    assert "/Volumes/payments_dev/landing/s3_batch_source/clean" in sql


def test_s3_copy_into_does_not_force_reload() -> None:
    """COPY INTO must retain default file-level idempotency."""

    path = ROOT / "sql" / "ingestion" / "03c_payment_transactions_s3.sql"

    sql = path.read_text(encoding="utf-8").upper()

    assert "COPY INTO" in sql
    assert "FORCE = TRUE" not in sql
    assert "FORCE=TRUE" not in sql


def test_s3_ingestion_captures_file_lineage() -> None:
    """Physical source-file metadata must be retained."""

    path = ROOT / "sql" / "ingestion" / "03c_payment_transactions_s3.sql"

    sql = path.read_text(encoding="utf-8")

    assert "_metadata.file_path" in sql
    assert "_metadata.file_name" in sql
    assert "source_file" in sql
    assert "source_file_name" in sql


def test_s3_ingestion_captures_ingestion_timestamp() -> None:
    """The ingestion timestamp must be retained for operational lineage."""

    path = ROOT / "sql" / "ingestion" / "03c_payment_transactions_s3.sql"

    sql = path.read_text(encoding="utf-8").lower()

    assert "current_timestamp()" in sql
    assert "ingested_at" in sql


def test_s3_reconciliation_sql_exists() -> None:
    """Step 3C must include source-to-target reconciliation."""

    path = ROOT / "sql" / "ingestion" / "03c_reconcile_batch_ingestion.sql"

    assert path.exists()


def test_reconciliation_compares_both_ingestion_paths() -> None:
    """Reconciliation must compare Step 3A and Step 3C tables."""

    path = ROOT / "sql" / "ingestion" / "03c_reconcile_batch_ingestion.sql"

    sql = path.read_text(encoding="utf-8")

    assert "payment_transactions_batch" in sql
    assert "payment_transactions_batch_s3" in sql


def test_reconciliation_checks_both_directions() -> None:
    """Full business comparison must run in both directions."""

    path = ROOT / "sql" / "ingestion" / "03c_reconcile_batch_ingestion.sql"

    sql = path.read_text(encoding="utf-8").upper()

    assert sql.count("EXCEPT ALL") >= 2


def test_reconciliation_checks_duplicates() -> None:
    """The reconciliation SQL must detect duplicate transaction IDs."""

    path = ROOT / "sql" / "ingestion" / "03c_reconcile_batch_ingestion.sql"

    sql = path.read_text(encoding="utf-8").upper()

    assert "HAVING COUNT(*) > 1" in sql
