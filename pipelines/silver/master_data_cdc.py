"""AUTO CDC processing for mutable customer, account, and merchant dimensions.

This module implements:

- initial snapshot hydration
- incremental CDC ingestion with Auto Loader
- CDC data-quality validation
- out-of-order change processing
- delete handling
- SCD Type 1 current-state tables
- SCD Type 2 history tables

The synthetic source deliberately includes out-of-order CDC records.
record_version is therefore used as the AUTO CDC sequencing column so that
logical business order, rather than physical file-arrival order, determines
the final state.
"""

from dq_rules import (
    ACCOUNT_RULES,
    CUSTOMER_RULES,
    MERCHANT_RULES,
)
from pyspark import pipelines as dp
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    DateType,
    DecimalType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# ============================================================================
# SOURCE PATHS
# ============================================================================

CUSTOMER_CDC_PATH = "/Volumes/payments_dev/landing/postgres_batch_source/cdc/customers"

ACCOUNT_CDC_PATH = "/Volumes/payments_dev/landing/postgres_batch_source/cdc/accounts"

MERCHANT_CDC_PATH = "/Volumes/payments_dev/landing/postgres_batch_source/cdc/merchants"


# ============================================================================
# CDC SOURCE SCHEMAS
# ============================================================================

CUSTOMER_SCHEMA = StructType(
    [
        StructField(
            "customer_id",
            StringType(),
            True,
        ),
        StructField(
            "first_name",
            StringType(),
            True,
        ),
        StructField(
            "last_name",
            StringType(),
            True,
        ),
        StructField(
            "date_of_birth",
            DateType(),
            True,
        ),
        StructField(
            "email",
            StringType(),
            True,
        ),
        StructField(
            "phone",
            StringType(),
            True,
        ),
        StructField(
            "address_line_1",
            StringType(),
            True,
        ),
        StructField(
            "city",
            StringType(),
            True,
        ),
        StructField(
            "state",
            StringType(),
            True,
        ),
        StructField(
            "postcode",
            StringType(),
            True,
        ),
        StructField(
            "country",
            StringType(),
            True,
        ),
        StructField(
            "risk_rating",
            StringType(),
            True,
        ),
        StructField(
            "kyc_status",
            StringType(),
            True,
        ),
        StructField(
            "status",
            StringType(),
            True,
        ),
        StructField(
            "record_version",
            IntegerType(),
            True,
        ),
        StructField(
            "source_updated_at",
            TimestampType(),
            True,
        ),
        StructField(
            "is_deleted",
            BooleanType(),
            True,
        ),
    ]
)


ACCOUNT_SCHEMA = StructType(
    [
        StructField(
            "account_id",
            StringType(),
            True,
        ),
        StructField(
            "customer_id",
            StringType(),
            True,
        ),
        StructField(
            "account_type",
            StringType(),
            True,
        ),
        StructField(
            "currency",
            StringType(),
            True,
        ),
        StructField(
            "status",
            StringType(),
            True,
        ),
        StructField(
            "opened_date",
            DateType(),
            True,
        ),
        StructField(
            "current_balance",
            DecimalType(18, 2),
            True,
        ),
        StructField(
            "record_version",
            IntegerType(),
            True,
        ),
        StructField(
            "source_updated_at",
            TimestampType(),
            True,
        ),
        StructField(
            "is_deleted",
            BooleanType(),
            True,
        ),
    ]
)


MERCHANT_SCHEMA = StructType(
    [
        StructField(
            "merchant_id",
            StringType(),
            True,
        ),
        StructField(
            "merchant_name",
            StringType(),
            True,
        ),
        StructField(
            "merchant_category_code",
            StringType(),
            True,
        ),
        StructField(
            "city",
            StringType(),
            True,
        ),
        StructField(
            "country",
            StringType(),
            True,
        ),
        StructField(
            "risk_rating",
            StringType(),
            True,
        ),
        StructField(
            "status",
            StringType(),
            True,
        ),
        StructField(
            "record_version",
            IntegerType(),
            True,
        ),
        StructField(
            "source_updated_at",
            TimestampType(),
            True,
        ),
        StructField(
            "is_deleted",
            BooleanType(),
            True,
        ),
    ]
)


# ============================================================================
# COMMON HELPERS
# ============================================================================


def _spark() -> SparkSession:
    """Return the active Spark session managed by Lakeflow."""

    session = SparkSession.getActiveSession()

    if session is None:
        raise RuntimeError("No active Spark session is available")

    return session


def _read_cdc_csv(
    spark: SparkSession,
    path: str,
    schema: StructType,
) -> DataFrame:
    """Read an append-oriented CDC directory using Auto Loader."""

    return (
        spark.readStream.format("cloudFiles")
        .option(
            "cloudFiles.format",
            "csv",
        )
        .option(
            "cloudFiles.includeExistingFiles",
            "true",
        )
        .option(
            "header",
            "true",
        )
        .schema(schema)
        .load(path)
        .withColumn(
            "source_file",
            F.col("_metadata.file_path"),
        )
        .withColumn(
            "source_file_name",
            F.col("_metadata.file_name"),
        )
        .withColumn(
            "ingested_at",
            F.current_timestamp(),
        )
    )


def _after_snapshot_version(
    cdc: DataFrame,
    snapshot: DataFrame,
    key_column: str,
) -> DataFrame:
    """Keep only CDC versions newer than the baseline snapshot version.

    The synthetic CDC files contain the original version 1 row in addition
    to the later changes.

    The baseline snapshot has already hydrated version 1 into the target.

    This stream-static join removes the duplicated baseline version while
    retaining:

    - later updates
    - deletes
    - new business keys that were not present in the original snapshot
    """

    snapshot_versions = snapshot.select(
        F.col(key_column).alias("_snapshot_key"),
        F.col("record_version").alias("_snapshot_record_version"),
    ).alias("s")

    return (
        cdc.alias("c")
        .join(
            snapshot_versions,
            F.col(f"c.{key_column}") == F.col("s._snapshot_key"),
            "left",
        )
        .filter(
            F.col("s._snapshot_key").isNull()
            | (F.col("c.record_version") > F.col("s._snapshot_record_version"))
        )
        .select("c.*")
    )


# ============================================================================
# STANDARDIZATION HELPERS
# ============================================================================


def _standardize_customers(
    dataframe: DataFrame,
) -> DataFrame:
    """Standardize customer snapshot or CDC records."""

    return dataframe.select(
        F.col("customer_id"),
        F.trim(F.col("first_name")).alias("first_name"),
        F.trim(F.col("last_name")).alias("last_name"),
        F.col("date_of_birth"),
        F.lower(F.trim(F.col("email"))).alias("email"),
        F.trim(F.col("phone")).alias("phone"),
        F.trim(F.col("address_line_1")).alias("address_line_1"),
        F.trim(F.col("city")).alias("city"),
        F.upper(F.trim(F.col("state"))).alias("state"),
        F.trim(F.col("postcode")).alias("postcode"),
        F.upper(F.trim(F.col("country"))).alias("country"),
        F.upper(F.trim(F.col("risk_rating"))).alias("risk_rating"),
        F.upper(F.trim(F.col("kyc_status"))).alias("kyc_status"),
        F.upper(F.trim(F.col("status"))).alias("customer_status"),
        F.col("record_version"),
        F.col("source_updated_at"),
        F.col("is_deleted"),
        F.col("source_file"),
        F.col("source_file_name"),
        F.col("ingested_at").alias("source_ingested_at"),
    )


def _standardize_accounts(
    dataframe: DataFrame,
) -> DataFrame:
    """Standardize account snapshot or CDC records."""

    return dataframe.select(
        F.col("account_id"),
        F.col("customer_id"),
        F.upper(F.trim(F.col("account_type"))).alias("account_type"),
        F.upper(F.trim(F.col("currency"))).alias("account_currency"),
        F.upper(F.trim(F.col("status"))).alias("account_status"),
        F.col("opened_date"),
        F.col("current_balance"),
        F.col("record_version"),
        F.col("source_updated_at"),
        F.col("is_deleted"),
        F.col("source_file"),
        F.col("source_file_name"),
        F.col("ingested_at").alias("source_ingested_at"),
    )


def _standardize_merchants(
    dataframe: DataFrame,
) -> DataFrame:
    """Standardize merchant snapshot or CDC records."""

    return dataframe.select(
        F.col("merchant_id"),
        F.trim(F.col("merchant_name")).alias("merchant_name"),
        F.trim(F.col("merchant_category_code")).alias("merchant_category_code"),
        F.trim(F.col("city")).alias("merchant_city"),
        F.upper(F.trim(F.col("country"))).alias("merchant_country"),
        F.upper(F.trim(F.col("risk_rating"))).alias("merchant_risk_rating"),
        F.upper(F.trim(F.col("status"))).alias("merchant_status"),
        F.col("record_version"),
        F.col("source_updated_at"),
        F.col("is_deleted"),
        F.col("source_file"),
        F.col("source_file_name"),
        F.col("ingested_at").alias("source_ingested_at"),
    )


# ============================================================================
# CUSTOMER SNAPSHOT SOURCE
#
# IMPORTANT:
# This is a STREAMING temporary view.
#
# The AUTO CDC once=True hydration flow still consumes a streaming view.
# The ONCE property controls execution frequency; it does not make this
# source a batch temporary view.
# ============================================================================


@dp.temporary_view(
    name="customers_snapshot_seed",
    comment=(
        "Validated streaming view of the baseline customer snapshot "
        "used to hydrate AUTO CDC targets."
    ),
)
@dp.expect_all_or_fail(CUSTOMER_RULES)
def customers_snapshot_seed():
    """Stream the baseline customer snapshot for initial hydration."""

    spark = _spark()

    snapshot = spark.readStream.table("payments_dev.ingestion.customers_snapshot")

    return _standardize_customers(snapshot)


# ============================================================================
# CUSTOMER CONTINUOUS CDC SOURCE
# ============================================================================


@dp.temporary_view(
    name="customers_cdc_validated",
    comment=(
        "Validated incremental customer CDC records newer than the baseline snapshot version."
    ),
)
@dp.expect_all_or_drop(CUSTOMER_RULES)
def customers_cdc_validated():
    """Stream validated customer changes after the baseline version."""

    spark = _spark()

    cdc = _read_cdc_csv(
        spark,
        CUSTOMER_CDC_PATH,
        CUSTOMER_SCHEMA,
    )

    # ------------------------------------------------------------------------
    # IMPORTANT:
    # Keep this as a BATCH read.
    #
    # The CDC source above is streaming.
    # This snapshot is a static lookup used in a stream-static join.
    # ------------------------------------------------------------------------

    snapshot = spark.read.table("payments_dev.ingestion.customers_snapshot")

    incremental = _after_snapshot_version(
        cdc=cdc,
        snapshot=snapshot,
        key_column="customer_id",
    )

    return _standardize_customers(incremental)


# ============================================================================
# ACCOUNT SNAPSHOT SOURCE
# ============================================================================


@dp.temporary_view(
    name="accounts_snapshot_seed",
    comment=(
        "Validated streaming view of the baseline account snapshot "
        "used to hydrate AUTO CDC targets."
    ),
)
@dp.expect_all_or_fail(ACCOUNT_RULES)
def accounts_snapshot_seed():
    """Stream the baseline account snapshot for initial hydration."""

    spark = _spark()

    snapshot = spark.readStream.table("payments_dev.ingestion.accounts_snapshot")

    return _standardize_accounts(snapshot)


# ============================================================================
# ACCOUNT CONTINUOUS CDC SOURCE
# ============================================================================


@dp.temporary_view(
    name="accounts_cdc_validated",
    comment=("Validated incremental account CDC records newer than the baseline snapshot version."),
)
@dp.expect_all_or_drop(ACCOUNT_RULES)
def accounts_cdc_validated():
    """Stream validated account changes after the baseline version."""

    spark = _spark()

    cdc = _read_cdc_csv(
        spark,
        ACCOUNT_CDC_PATH,
        ACCOUNT_SCHEMA,
    )

    # Static snapshot lookup for the stream-static version comparison.
    snapshot = spark.read.table("payments_dev.ingestion.accounts_snapshot")

    incremental = _after_snapshot_version(
        cdc=cdc,
        snapshot=snapshot,
        key_column="account_id",
    )

    return _standardize_accounts(incremental)


# ============================================================================
# MERCHANT SNAPSHOT SOURCE
# ============================================================================


@dp.temporary_view(
    name="merchants_snapshot_seed",
    comment=(
        "Validated streaming view of the baseline merchant snapshot "
        "used to hydrate AUTO CDC targets."
    ),
)
@dp.expect_all_or_fail(MERCHANT_RULES)
def merchants_snapshot_seed():
    """Stream the baseline merchant snapshot for initial hydration."""

    spark = _spark()

    snapshot = spark.readStream.table("payments_dev.ingestion.merchants_snapshot")

    return _standardize_merchants(snapshot)


# ============================================================================
# MERCHANT CONTINUOUS CDC SOURCE
# ============================================================================


@dp.temporary_view(
    name="merchants_cdc_validated",
    comment=(
        "Validated incremental merchant CDC records newer than the baseline snapshot version."
    ),
)
@dp.expect_all_or_drop(MERCHANT_RULES)
def merchants_cdc_validated():
    """Stream validated merchant changes after the baseline version."""

    spark = _spark()

    cdc = _read_cdc_csv(
        spark,
        MERCHANT_CDC_PATH,
        MERCHANT_SCHEMA,
    )

    # Static snapshot lookup for the stream-static version comparison.
    snapshot = spark.read.table("payments_dev.ingestion.merchants_snapshot")

    incremental = _after_snapshot_version(
        cdc=cdc,
        snapshot=snapshot,
        key_column="merchant_id",
    )

    return _standardize_merchants(incremental)


# ============================================================================
# CUSTOMER — SCD TYPE 1 CURRENT STATE
# ============================================================================


dp.create_streaming_table(
    name="customers_current",
    comment=(
        "Current customer state maintained with Lakeflow AUTO CDC using SCD Type 1 semantics."
    ),
    table_properties={
        "quality": "silver",
        "domain": "customer",
        "trust_level": "trusted",
        "delta.enableRowTracking": "true",
        "delta.enableChangeDataFeed": "true",
        "pipelines.cdc.tombstoneGCThresholdInSeconds": "604800",
    },
)


dp.create_auto_cdc_flow(
    name="customers_current_snapshot_seed",
    target="customers_current",
    source="customers_snapshot_seed",
    keys=[
        "customer_id",
    ],
    sequence_by="record_version",
    apply_as_deletes=F.expr("is_deleted = true"),
    except_column_list=[
        "is_deleted",
    ],
    stored_as_scd_type=1,
    once=True,
)


dp.create_auto_cdc_flow(
    name="customers_current_incremental_cdc",
    target="customers_current",
    source="customers_cdc_validated",
    keys=[
        "customer_id",
    ],
    sequence_by="record_version",
    apply_as_deletes=F.expr("is_deleted = true"),
    except_column_list=[
        "is_deleted",
    ],
    stored_as_scd_type=1,
)


# ============================================================================
# CUSTOMER — SCD TYPE 2 HISTORY
# ============================================================================


dp.create_streaming_table(
    name="customer_history",
    comment=(
        "Historical customer versions maintained with Lakeflow AUTO CDC using SCD Type 2 semantics."
    ),
    table_properties={
        "quality": "silver",
        "domain": "customer",
        "trust_level": "historical",
        "delta.enableRowTracking": "true",
        "delta.enableChangeDataFeed": "true",
        "pipelines.cdc.tombstoneGCThresholdInSeconds": "604800",
    },
)


dp.create_auto_cdc_flow(
    name="customer_history_snapshot_seed",
    target="customer_history",
    source="customers_snapshot_seed",
    keys=[
        "customer_id",
    ],
    sequence_by="record_version",
    apply_as_deletes=F.expr("is_deleted = true"),
    except_column_list=[
        "is_deleted",
    ],
    stored_as_scd_type="2",
    once=True,
)


dp.create_auto_cdc_flow(
    name="customer_history_incremental_cdc",
    target="customer_history",
    source="customers_cdc_validated",
    keys=[
        "customer_id",
    ],
    sequence_by="record_version",
    apply_as_deletes=F.expr("is_deleted = true"),
    except_column_list=[
        "is_deleted",
    ],
    stored_as_scd_type="2",
)


# ============================================================================
# ACCOUNT — SCD TYPE 1 CURRENT STATE
# ============================================================================


dp.create_streaming_table(
    name="accounts_current",
    comment=("Current account state maintained with Lakeflow AUTO CDC using SCD Type 1 semantics."),
    table_properties={
        "quality": "silver",
        "domain": "account",
        "trust_level": "trusted",
        "delta.enableRowTracking": "true",
        "delta.enableChangeDataFeed": "true",
        "pipelines.cdc.tombstoneGCThresholdInSeconds": "604800",
    },
)


dp.create_auto_cdc_flow(
    name="accounts_current_snapshot_seed",
    target="accounts_current",
    source="accounts_snapshot_seed",
    keys=[
        "account_id",
    ],
    sequence_by="record_version",
    apply_as_deletes=F.expr("is_deleted = true"),
    except_column_list=[
        "is_deleted",
    ],
    stored_as_scd_type=1,
    once=True,
)


dp.create_auto_cdc_flow(
    name="accounts_current_incremental_cdc",
    target="accounts_current",
    source="accounts_cdc_validated",
    keys=[
        "account_id",
    ],
    sequence_by="record_version",
    apply_as_deletes=F.expr("is_deleted = true"),
    except_column_list=[
        "is_deleted",
    ],
    stored_as_scd_type=1,
)


# ============================================================================
# ACCOUNT — SCD TYPE 2 HISTORY
# ============================================================================


dp.create_streaming_table(
    name="account_history",
    comment=(
        "Historical account versions maintained with Lakeflow AUTO CDC using SCD Type 2 semantics."
    ),
    table_properties={
        "quality": "silver",
        "domain": "account",
        "trust_level": "historical",
        "delta.enableRowTracking": "true",
        "delta.enableChangeDataFeed": "true",
        "pipelines.cdc.tombstoneGCThresholdInSeconds": "604800",
    },
)


dp.create_auto_cdc_flow(
    name="account_history_snapshot_seed",
    target="account_history",
    source="accounts_snapshot_seed",
    keys=[
        "account_id",
    ],
    sequence_by="record_version",
    apply_as_deletes=F.expr("is_deleted = true"),
    except_column_list=[
        "is_deleted",
    ],
    stored_as_scd_type="2",
    once=True,
)


dp.create_auto_cdc_flow(
    name="account_history_incremental_cdc",
    target="account_history",
    source="accounts_cdc_validated",
    keys=[
        "account_id",
    ],
    sequence_by="record_version",
    apply_as_deletes=F.expr("is_deleted = true"),
    except_column_list=[
        "is_deleted",
    ],
    stored_as_scd_type="2",
)


# ============================================================================
# MERCHANT — SCD TYPE 1 CURRENT STATE
# ============================================================================


dp.create_streaming_table(
    name="merchants_current",
    comment=(
        "Current merchant state maintained with Lakeflow AUTO CDC using SCD Type 1 semantics."
    ),
    table_properties={
        "quality": "silver",
        "domain": "merchant",
        "trust_level": "trusted",
        "delta.enableRowTracking": "true",
        "delta.enableChangeDataFeed": "true",
        "pipelines.cdc.tombstoneGCThresholdInSeconds": "604800",
    },
)


dp.create_auto_cdc_flow(
    name="merchants_current_snapshot_seed",
    target="merchants_current",
    source="merchants_snapshot_seed",
    keys=[
        "merchant_id",
    ],
    sequence_by="record_version",
    apply_as_deletes=F.expr("is_deleted = true"),
    except_column_list=[
        "is_deleted",
    ],
    stored_as_scd_type=1,
    once=True,
)


dp.create_auto_cdc_flow(
    name="merchants_current_incremental_cdc",
    target="merchants_current",
    source="merchants_cdc_validated",
    keys=[
        "merchant_id",
    ],
    sequence_by="record_version",
    apply_as_deletes=F.expr("is_deleted = true"),
    except_column_list=[
        "is_deleted",
    ],
    stored_as_scd_type=1,
)


# ============================================================================
# MERCHANT — SCD TYPE 2 HISTORY
# ============================================================================


dp.create_streaming_table(
    name="merchant_history",
    comment=(
        "Historical merchant versions maintained with Lakeflow AUTO CDC using SCD Type 2 semantics."
    ),
    table_properties={
        "quality": "silver",
        "domain": "merchant",
        "trust_level": "historical",
        "delta.enableRowTracking": "true",
        "delta.enableChangeDataFeed": "true",
        "pipelines.cdc.tombstoneGCThresholdInSeconds": "604800",
    },
)


dp.create_auto_cdc_flow(
    name="merchant_history_snapshot_seed",
    target="merchant_history",
    source="merchants_snapshot_seed",
    keys=[
        "merchant_id",
    ],
    sequence_by="record_version",
    apply_as_deletes=F.expr("is_deleted = true"),
    except_column_list=[
        "is_deleted",
    ],
    stored_as_scd_type="2",
    once=True,
)


dp.create_auto_cdc_flow(
    name="merchant_history_incremental_cdc",
    target="merchant_history",
    source="merchants_cdc_validated",
    keys=[
        "merchant_id",
    ],
    sequence_by="record_version",
    apply_as_deletes=F.expr("is_deleted = true"),
    except_column_list=[
        "is_deleted",
    ],
    stored_as_scd_type="2",
)
