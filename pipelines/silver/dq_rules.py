"""Reusable Lakeflow data-quality rules for Silver payments datasets."""

from collections.abc import Mapping

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

RuleSet = Mapping[str, str]


PAYMENT_EVENT_RULES = {
    "event_id_present": ("event_id IS NOT NULL AND trim(event_id) <> ''"),
    "transaction_id_present": ("transaction_id IS NOT NULL AND trim(transaction_id) <> ''"),
    "account_id_present": ("account_id IS NOT NULL AND trim(account_id) <> ''"),
    "merchant_id_present": ("merchant_id IS NOT NULL AND trim(merchant_id) <> ''"),
    "event_timestamp_present": ("event_timestamp IS NOT NULL"),
    "transaction_timestamp_present": ("transaction_event_timestamp IS NOT NULL"),
    "sequence_number_positive": ("sequence_number IS NOT NULL AND sequence_number > 0"),
    "amount_positive": ("amount IS NOT NULL AND amount > 0"),
    "currency_code_valid": ("currency IS NOT NULL AND currency RLIKE '^[A-Z]{3}$'"),
    "event_type_valid": ("event_type IN ('AUTHORIZATION', 'DECLINE', 'SETTLEMENT', 'REVERSAL', 'REFUND')"),
    "channel_valid": ("channel IN ('POS', 'ECOMMERCE', 'MOBILE', 'ATM')"),
    "payment_method_valid": ("payment_method IN ('DEBIT_CARD', 'CREDIT_CARD', 'DIGITAL_WALLET', 'BANK_TRANSFER')"),
    "transaction_status_valid": ("transaction_status IN ('AUTHORIZED', 'DECLINED', 'SETTLED', 'REVERSED', 'REFUNDED')"),
    "country_code_valid": ("country IS NOT NULL AND country RLIKE '^[A-Z]{2}$'"),
    "payload_parsed": ("parse_status = 'PARSED'"),
    "kafka_lineage_present": ("kafka_topic IS NOT NULL AND kafka_partition IS NOT NULL AND kafka_offset IS NOT NULL"),
}


PAYMENT_TRANSACTION_RULES = {
    "transaction_id_present": ("transaction_id IS NOT NULL AND trim(transaction_id) <> ''"),
    "account_id_present": ("account_id IS NOT NULL AND trim(account_id) <> ''"),
    "merchant_id_present": ("merchant_id IS NOT NULL AND trim(merchant_id) <> ''"),
    "event_timestamp_present": ("event_timestamp IS NOT NULL"),
    "amount_positive": ("amount IS NOT NULL AND amount > 0"),
    "currency_code_valid": ("currency IS NOT NULL AND currency RLIKE '^[A-Z]{3}$'"),
    "channel_valid": ("channel IN ('POS', 'ECOMMERCE', 'MOBILE', 'ATM')"),
    "payment_method_valid": ("payment_method IN ('DEBIT_CARD', 'CREDIT_CARD', 'DIGITAL_WALLET', 'BANK_TRANSFER')"),
    "transaction_status_valid": ("transaction_status IN ('AUTHORIZED', 'DECLINED', 'SETTLED', 'REVERSED', 'REFUNDED')"),
    "country_code_valid": ("country IS NOT NULL AND country RLIKE '^[A-Z]{2}$'"),
}


CUSTOMER_RULES = {
    "customer_id_present": ("customer_id IS NOT NULL AND trim(customer_id) <> ''"),
    "country_code_valid": ("country IS NOT NULL AND country RLIKE '^[A-Z]{2}$'"),
    "risk_rating_valid": ("risk_rating IN ('LOW', 'MEDIUM', 'HIGH')"),
    "kyc_status_valid": ("kyc_status IN ('PENDING', 'VERIFIED', 'REJECTED')"),
    "customer_status_valid": ("customer_status IN ('ACTIVE', 'SUSPENDED', 'CLOSED')"),
    "record_version_valid": ("record_version IS NOT NULL AND record_version >= 1"),
    "source_updated_at_present": ("source_updated_at IS NOT NULL"),
}


ACCOUNT_RULES = {
    "account_id_present": ("account_id IS NOT NULL AND trim(account_id) <> ''"),
    "customer_id_present": ("customer_id IS NOT NULL AND trim(customer_id) <> ''"),
    "account_type_valid": ("account_type IN ('CHECKING', 'SAVINGS', 'CREDIT_CARD')"),
    "account_currency_valid": ("account_currency IS NOT NULL AND account_currency RLIKE '^[A-Z]{3}$'"),
    "account_status_valid": ("account_status IN ('ACTIVE', 'BLOCKED', 'CLOSED')"),
    "opened_date_present": ("opened_date IS NOT NULL"),
    "record_version_valid": ("record_version IS NOT NULL AND record_version >= 1"),
    "source_updated_at_present": ("source_updated_at IS NOT NULL"),
}


MERCHANT_RULES = {
    "merchant_id_present": ("merchant_id IS NOT NULL AND trim(merchant_id) <> ''"),
    "merchant_name_present": ("merchant_name IS NOT NULL AND trim(merchant_name) <> ''"),
    "merchant_category_code_valid": ("merchant_category_code RLIKE '^[0-9]{4}$'"),
    "merchant_country_valid": ("merchant_country IS NOT NULL AND merchant_country RLIKE '^[A-Z]{2}$'"),
    "merchant_risk_rating_valid": ("merchant_risk_rating IN ('LOW', 'MEDIUM', 'HIGH')"),
    "merchant_status_valid": ("merchant_status IN ('ACTIVE', 'SUSPENDED', 'CLOSED')"),
    "record_version_valid": ("record_version IS NOT NULL AND record_version >= 1"),
    "source_updated_at_present": ("source_updated_at IS NOT NULL"),
}


FRAUD_CASE_RULES = {
    "case_id_present": ("case_id IS NOT NULL AND trim(case_id) <> ''"),
    "transaction_id_present": ("transaction_id IS NOT NULL AND trim(transaction_id) <> ''"),
    "opened_at_present": ("opened_at IS NOT NULL"),
    "fraud_case_status_valid": ("fraud_case_status IN ('OPEN', 'INVESTIGATING', 'CLOSED')"),
    "fraud_outcome_valid": (
        "fraud_outcome IS NULL OR fraud_outcome IN ('CONFIRMED_FRAUD', 'LEGITIMATE', 'UNDETERMINED')"
    ),
    "closed_case_has_closed_at": ("fraud_case_status <> 'CLOSED' OR closed_at IS NOT NULL"),
}


def add_quality_columns(
    dataframe: DataFrame,
    rules: RuleSet,
) -> DataFrame:
    """Add failed-rule, quarantine, status, and audit columns."""

    failed_rules = [
        F.when(
            ~F.coalesce(
                F.expr(constraint),
                F.lit(False),
            ),
            F.lit(rule_name),
        )
        for rule_name, constraint in rules.items()
    ]

    with_failures = dataframe.withColumn(
        "dq_failed_rules",
        F.filter(
            F.array(*failed_rules),
            lambda rule: rule.isNotNull(),
        ),
    )

    return (
        with_failures.withColumn(
            "is_quarantined",
            F.size(F.col("dq_failed_rules")) > 0,
        )
        .withColumn(
            "dq_status",
            F.when(
                F.col("is_quarantined"),
                F.lit("QUARANTINED"),
            ).otherwise(F.lit("VALID")),
        )
        .withColumn(
            "dq_checked_at",
            F.current_timestamp(),
        )
    )
