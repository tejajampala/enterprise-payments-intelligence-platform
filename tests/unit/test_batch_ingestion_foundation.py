"""Tests for the Milestone 3 batch-ingestion foundation."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_ingestion_bundle_resource_exists() -> None:
    """The bundle resource definition for batch ingestion must exist."""

    assert (ROOT / "bundle" / "resources" / "ingestion_foundation.yml").exists()


def test_databricks_bundle_includes_resource_files() -> None:
    """The root bundle must include resource YAML files."""

    with (ROOT / "databricks.yml").open(
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    assert "bundle/resources/*.yml" in config["include"]


def test_databricks_bundle_excludes_generated_data() -> None:
    """Generated datasets must not be synchronized as bundle source files."""

    with (ROOT / "databricks.yml").open(
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    assert "data/**" in config["sync"]["exclude"]


def test_bundle_defines_existing_catalog_variable() -> None:
    """The application should reference the existing development catalog."""

    with (ROOT / "databricks.yml").open(
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    assert config["variables"]["catalog_name"]["default"] == "payments_dev"


def test_bundle_skips_development_schema_prefix() -> None:
    """Development deployments must retain stable schema names."""

    with (ROOT / "databricks.yml").open(
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    assert config["experimental"]["skip_name_prefix_for_schema"] is True


def test_ingestion_foundation_uses_existing_catalog() -> None:
    """Schemas should use the existing catalog instead of creating one."""

    path = ROOT / "bundle" / "resources" / "ingestion_foundation.yml"

    with path.open(
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    resources = config["resources"]

    assert "catalogs" not in resources

    assert resources["schemas"]["landing_schema"]["catalog_name"] == "${var.catalog_name}"

    assert resources["schemas"]["ingestion_schema"]["catalog_name"] == "${var.catalog_name}"


def test_landing_schema_has_expected_name() -> None:
    """The governed file landing schema should be named landing."""

    path = ROOT / "bundle" / "resources" / "ingestion_foundation.yml"

    with path.open(
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    landing_schema = config["resources"]["schemas"]["landing_schema"]

    assert landing_schema["name"] == "landing"


def test_ingestion_schema_has_expected_name() -> None:
    """The raw ingestion-table schema should be named ingestion."""

    path = ROOT / "bundle" / "resources" / "ingestion_foundation.yml"

    with path.open(
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    ingestion_schema = config["resources"]["schemas"]["ingestion_schema"]

    assert ingestion_schema["name"] == "ingestion"


def test_ingestion_foundation_defines_managed_volume() -> None:
    """The development landing volume should be a managed UC volume."""

    path = ROOT / "bundle" / "resources" / "ingestion_foundation.yml"

    with path.open(
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    volume = config["resources"]["volumes"]["batch_source_volume"]

    assert volume["name"] == "batch_source"
    assert volume["catalog_name"] == "${var.catalog_name}"
    assert volume["schema_name"] == "${resources.schemas.landing_schema.name}"
    assert volume["volume_type"] == "MANAGED"


def test_copy_into_sql_exists() -> None:
    """The historical transaction COPY INTO SQL must exist."""

    sql_path = ROOT / "sql" / "ingestion" / "03a_payment_transactions_copy_into.sql"

    assert sql_path.exists()


def test_copy_into_targets_expected_table() -> None:
    """The batch ingestion SQL should target the expected Delta table."""

    sql_path = ROOT / "sql" / "ingestion" / "03a_payment_transactions_copy_into.sql"

    sql = sql_path.read_text(
        encoding="utf-8",
    )

    assert "payments_dev.ingestion.payment_transactions_batch" in sql


def test_copy_into_reads_from_managed_volume() -> None:
    """The ingestion SQL must read from the governed landing volume."""

    sql_path = ROOT / "sql" / "ingestion" / "03a_payment_transactions_copy_into.sql"

    sql = sql_path.read_text(
        encoding="utf-8",
    )

    assert "/Volumes/payments_dev/landing/batch_source/historical_transactions/clean" in sql


def test_copy_into_uses_json_source_format() -> None:
    """Historical transaction source files are JSON Lines."""

    sql_path = ROOT / "sql" / "ingestion" / "03a_payment_transactions_copy_into.sql"

    sql = sql_path.read_text(
        encoding="utf-8",
    ).upper()

    assert "FILEFORMAT = JSON" in sql


def test_copy_into_recursively_reads_partition_directories() -> None:
    """COPY INTO must discover event_date partition folders recursively."""

    sql_path = ROOT / "sql" / "ingestion" / "03a_payment_transactions_copy_into.sql"

    sql = sql_path.read_text(
        encoding="utf-8",
    )

    assert "'recursiveFileLookup' = 'true'" in sql


def test_copy_into_is_idempotent_by_default() -> None:
    """FORCE must not be enabled because it would reload processed files."""

    sql_path = ROOT / "sql" / "ingestion" / "03a_payment_transactions_copy_into.sql"

    sql = sql_path.read_text(
        encoding="utf-8",
    ).upper()

    assert "COPY INTO" in sql

    # FORCE = TRUE would deliberately reload files that COPY INTO
    # has already processed.
    assert "FORCE = TRUE" not in sql
    assert "FORCE=TRUE" not in sql


def test_ingestion_tracks_source_file_path() -> None:
    """Rows must capture their physical source-file path for lineage."""

    sql_path = ROOT / "sql" / "ingestion" / "03a_payment_transactions_copy_into.sql"

    sql = sql_path.read_text(
        encoding="utf-8",
    )

    assert "_metadata.file_path AS source_file" in sql


def test_ingestion_tracks_source_file_name() -> None:
    """Rows must capture the source filename for troubleshooting."""

    sql_path = ROOT / "sql" / "ingestion" / "03a_payment_transactions_copy_into.sql"

    sql = sql_path.read_text(
        encoding="utf-8",
    )

    assert "_metadata.file_name AS source_file_name" in sql


def test_ingestion_tracks_ingestion_timestamp() -> None:
    """Rows must record when they entered the ingestion table."""

    sql_path = ROOT / "sql" / "ingestion" / "03a_payment_transactions_copy_into.sql"

    sql = sql_path.read_text(
        encoding="utf-8",
    ).lower()

    assert "current_timestamp() as ingested_at" in sql


def test_batch_table_uses_delta() -> None:
    """The raw batch ingestion table should use Delta Lake."""

    sql_path = ROOT / "sql" / "ingestion" / "03a_payment_transactions_copy_into.sql"

    sql = sql_path.read_text(
        encoding="utf-8",
    ).upper()

    assert "USING DELTA" in sql


def test_batch_table_contains_core_business_columns() -> None:
    """The ingestion table must retain the core transaction fields."""

    sql_path = ROOT / "sql" / "ingestion" / "03a_payment_transactions_copy_into.sql"

    sql = sql_path.read_text(
        encoding="utf-8",
    ).lower()

    required_columns = (
        "transaction_id",
        "account_id",
        "merchant_id",
        "event_timestamp",
        "amount",
        "currency",
        "channel",
        "payment_method",
        "status",
        "card_present",
        "device_id",
        "ip_address",
        "country",
        "source_file",
        "source_file_name",
        "ingested_at",
    )

    for column in required_columns:
        assert column in sql
