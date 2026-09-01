# Databricks notebook source

"""Milestone 11 — Fraud investigation knowledge and RAG evaluation data.

Creates:

- governed synthetic fraud investigation knowledge
- deterministic paragraph-aware chunks
- RAG evaluation dataset with expected documents
- expected facts for MLflow RetrievalSufficiency evaluation

No real customer or banking information is used.
"""

# COMMAND ----------

from datetime import UTC, datetime

from pyspark.sql import SparkSession

spark_session = SparkSession.getActiveSession()

if spark_session is None:
    raise RuntimeError("No active SparkSession is available for the fraud knowledge job")


dbutils.widgets.text(
    "catalog_name",
    "payments_dev",
)

CATALOG = dbutils.widgets.get("catalog_name")


AI_SCHEMA = "ai"

KNOWLEDGE_TABLE = f"{CATALOG}.{AI_SCHEMA}.fraud_investigation_knowledge_chunks"

EVALUATION_TABLE = f"{CATALOG}.{AI_SCHEMA}.rag_evaluation_dataset"


# COMMAND ----------
# Ensure schema exists.
#
# The bundle manages this schema as well, but CREATE IF NOT EXISTS makes the
# notebook independently reproducible.

spark_session.sql(
    f"""
    CREATE SCHEMA IF NOT EXISTS {CATALOG}.{AI_SCHEMA}
    """
)


# COMMAND ----------
# Synthetic fraud-investigation knowledge documents.

DOCUMENTS = [
    {
        "doc_id": "fraud_velocity_guide",
        "title": "Payment Velocity and Burst Activity Investigation Guide",
        "category": "velocity",
        "content": """
Payment velocity describes the number and value of payment attempts occurring
within a relatively short period. A sudden increase in transaction frequency
can be a fraud indicator when it materially differs from the customer's
established behaviour.

Investigators should review transaction counts over short and medium time
windows, including one-day and seven-day activity. Useful indicators include
repeated merchant attempts, rapidly increasing payment values, repeated
declines followed by approval, and activity spanning multiple payment
channels.

Velocity alone is not proof of fraud. Investigators should combine velocity
with customer history, merchant characteristics, payment channel,
card-present status, geography and other evidence before reaching a decision.

A burst of transactions shortly after an unusual change in account behaviour
can be particularly relevant to an account-takeover investigation.
""",
    },
    {
        "doc_id": "card_not_present_guide",
        "title": "Card-Not-Present Fraud Investigation Guide",
        "category": "card_not_present",
        "content": """
Card-not-present transactions occur when a physical payment card is not
presented to the merchant. Common examples include ecommerce payments and
some mobile transactions.

Card-not-present activity deserves additional review when combined with
unusual transaction value, new merchants, cross-border activity, rapidly
repeated payment attempts, unusual hours, or a change from the customer's
normal payment behaviour.

Investigators should compare the transaction with historical channel usage,
merchant history, geographic behaviour, recent declines and payment velocity.

Card-not-present status by itself does not establish fraud. The investigation
must consider the combination of available evidence.
""",
    },
    {
        "doc_id": "account_takeover_guide",
        "title": "Account Takeover Investigation Playbook",
        "category": "account_takeover",
        "content": """
Account takeover occurs when an unauthorized party obtains control of a
genuine customer's account or payment credentials.

Potential indicators include abrupt changes in spending behaviour, high
transaction velocity, card-not-present activity, new merchants, unusual
countries, unusual transaction times and repeated attempts immediately before
a successful transaction.

Investigators should evaluate combinations of signals instead of relying on
one isolated feature. A high-value payment to a new merchant following
multiple failed attempts deserves stronger review than an ordinary online
payment with no other behavioural change.

Investigators should compare recent activity with the customer's normal
historical behaviour and record which evidence supports the investigation
outcome.
""",
    },
    {
        "doc_id": "merchant_risk_guide",
        "title": "High-Risk Merchant Investigation Guide",
        "category": "merchant_risk",
        "content": """
Merchant risk is an important input when evaluating suspicious payments.
Elevated merchant risk can be associated with prior fraud patterns, unusual
transaction activity, high chargeback levels or previous investigations.

Transactions involving a high-risk or suspended merchant deserve increased
scrutiny, especially when combined with high payment value, customer
behaviour changes, card-not-present activity or cross-border behaviour.

Merchant risk alone must not automatically classify a payment as fraudulent.

Useful merchant evidence includes transaction volume, average transaction
amount, decline rates, card-not-present rates and changes relative to the
merchant's historical behaviour.
""",
    },
    {
        "doc_id": "duplicate_payment_guide",
        "title": "Duplicate Payment and Event Delivery Investigation Guide",
        "category": "duplicate",
        "content": """
A duplicate event delivery is not automatically a duplicate business payment.

Distributed streaming systems can deliver the same logical event more than
once. Investigators and downstream systems must distinguish physical delivery
duplicates from genuine repeated customer payment attempts.

The event_id identifies a logical payment event. Multiple physical deliveries
with the same event_id should normally be deduplicated before trusted business
analysis.

The transaction_id identifies the business payment transaction. Kafka replay,
retry or duplicate delivery should not be interpreted as additional customer
payment behaviour.

When apparent duplicates occur, investigators should compare event_id,
transaction_id, event timestamps, Kafka partition and offset information, and
delivery metadata before concluding that multiple payments occurred.
""",
    },
    {
        "doc_id": "cross_border_guide",
        "title": "Cross-Border Payment Investigation Guide",
        "category": "cross_border",
        "content": """
Cross-border activity can be a useful risk indicator when the payment country
differs from the customer's established geographic behaviour.

Additional scrutiny is appropriate when cross-border activity appears
together with high payment value, card-not-present activity, unusual
merchants, high payment velocity or repeated declines.

Cross-border status by itself does not establish fraud because customers can
legitimately travel or purchase from overseas merchants.

Investigators should compare the current transaction with recent geographic
history and determine whether it represents a meaningful behavioural change.
""",
    },
    {
        "doc_id": "decline_pattern_guide",
        "title": "Repeated Declines and Approval Pattern Guide",
        "category": "declines",
        "content": """
Repeated payment declines can result from credential testing, incorrect
payment details, insufficient funds or legitimate customer behaviour.

Several declined attempts followed by a successful payment may be relevant
when combined with high velocity, unusual merchant behaviour,
card-not-present activity or unusual geography.

Investigators should examine the timing and values of the declined attempts,
whether payment amounts changed, whether merchants changed and whether the
eventual approved payment differs from historical behaviour.

Declines must be interpreted as one signal within the broader fraud
investigation rather than as independent proof of fraud.
""",
    },
    {
        "doc_id": "decision_standard_guide",
        "title": "Fraud Investigation Evidence and Decision Standard",
        "category": "decisioning",
        "content": """
Fraud investigation decisions should be evidence-based, explainable and
reproducible.

Investigators should use multiple independent signals where possible,
including transaction attributes, customer behaviour, merchant behaviour,
geographic patterns, payment channel, card-present status, velocity, declines
and fraud-case information.

Investigators must distinguish observed facts from hypotheses.

A fraud model probability or risk indicator is an investigation aid and must
not be described as definitive proof of fraud.

If the available evidence is insufficient, the appropriate conclusion is that
additional investigation is required. Investigation notes should identify the
evidence supporting the assessment as well as remaining uncertainty.
""",
    },
]


# COMMAND ----------
# Paragraph-aware deterministic chunking.

MAX_CHUNK_CHARACTERS = 1200


def chunk_document(
    text: str,
    max_characters: int = MAX_CHUNK_CHARACTERS,
) -> list[str]:
    """Split text while keeping paragraphs intact where possible."""

    paragraphs = [paragraph.strip() for paragraph in text.strip().split("\n\n") if paragraph.strip()]

    chunks: list[str] = []

    current_paragraphs: list[str] = []

    current_length = 0

    for paragraph in paragraphs:
        paragraph_length = len(paragraph)

        proposed_length = current_length + paragraph_length + 2

        if current_paragraphs and proposed_length > max_characters:
            chunks.append("\n\n".join(current_paragraphs))

            current_paragraphs = []

            current_length = 0

        current_paragraphs.append(paragraph)

        current_length += paragraph_length + 2

    if current_paragraphs:
        chunks.append("\n\n".join(current_paragraphs))

    return chunks


# COMMAND ----------
# Materialize chunks.

generated_at = datetime.now(UTC)

knowledge_rows = []


for document in DOCUMENTS:
    chunks = chunk_document(document["content"])

    for chunk_number, chunk_text in enumerate(
        chunks,
        start=1,
    ):
        chunk_id = f"{document['doc_id']}_chunk_{chunk_number:03d}"

        knowledge_rows.append(
            {
                "chunk_id": chunk_id,
                "doc_id": document["doc_id"],
                "title": document["title"],
                "category": document["category"],
                "source_type": "synthetic_epip_playbook",
                "chunk_ordinal": chunk_number,
                "chunk_text": chunk_text,
                "updated_at": generated_at,
            }
        )


# COMMAND ----------
# Create governed Delta source table.
#
# CDF is required because this table drives the triggered Delta Sync index.

spark_session.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {KNOWLEDGE_TABLE} (

        chunk_id STRING NOT NULL,
        doc_id STRING NOT NULL,

        title STRING,
        category STRING,
        source_type STRING,

        chunk_ordinal INT,

        chunk_text STRING,

        updated_at TIMESTAMP,

        CONSTRAINT fraud_investigation_knowledge_pk
            PRIMARY KEY (chunk_id)

    )
    USING DELTA

    TBLPROPERTIES (
        'delta.enableChangeDataFeed' = 'true',
        'delta.enableRowTracking' = 'true'
    )
    """
)


# COMMAND ----------
# Upsert the deterministic knowledge set without rewriting unchanged rows.
#
# Why MERGE instead of DELETE + INSERT:
# - the table is the source for a triggered Delta Sync AI Search index
# - CDF should represent real knowledge changes, not every job rerun
# - unchanged chunks therefore keep their existing updated_at value and do not
#   trigger unnecessary embedding/index work.

knowledge_df = spark_session.createDataFrame(knowledge_rows)

incoming_view = "epip_m11_incoming_fraud_knowledge"
knowledge_df.createOrReplaceTempView(incoming_view)

spark_session.sql(
    f"""
    MERGE INTO {KNOWLEDGE_TABLE} AS target
    USING {incoming_view} AS source
      ON target.chunk_id = source.chunk_id

    WHEN MATCHED AND (
           NOT (target.doc_id <=> source.doc_id)
        OR NOT (target.title <=> source.title)
        OR NOT (target.category <=> source.category)
        OR NOT (target.source_type <=> source.source_type)
        OR NOT (target.chunk_ordinal <=> source.chunk_ordinal)
        OR NOT (target.chunk_text <=> source.chunk_text)
    ) THEN UPDATE SET
        target.doc_id = source.doc_id,
        target.title = source.title,
        target.category = source.category,
        target.source_type = source.source_type,
        target.chunk_ordinal = source.chunk_ordinal,
        target.chunk_text = source.chunk_text,
        target.updated_at = source.updated_at

    WHEN NOT MATCHED THEN INSERT (
        chunk_id,
        doc_id,
        title,
        category,
        source_type,
        chunk_ordinal,
        chunk_text,
        updated_at
    ) VALUES (
        source.chunk_id,
        source.doc_id,
        source.title,
        source.category,
        source.source_type,
        source.chunk_ordinal,
        source.chunk_text,
        source.updated_at
    )

    WHEN NOT MATCHED BY SOURCE THEN DELETE
    """
)


# COMMAND ----------
# Evaluation dataset.
#
# expected_doc_id:
#   Used for deterministic Hit@1 / Recall@3 / MRR.
#
# expected_facts:
#   Used by MLflow RetrievalSufficiency.

EVALUATION_CASES = [
    {
        "query_id": "q001",
        "question": (
            "What should an investigator review when a customer suddenly makes many payments within a short period?"
        ),
        "expected_doc_id": "fraud_velocity_guide",
        "expected_facts": [
            "Review short and medium-term payment velocity.",
            "Review repeated payment attempts.",
            "Combine velocity with other fraud indicators.",
            "Velocity alone does not prove fraud.",
        ],
    },
    {
        "query_id": "q002",
        "question": ("What evidence is relevant when investigating a suspicious ecommerce card-not-present payment?"),
        "expected_doc_id": "card_not_present_guide",
        "expected_facts": [
            "Review customer historical channel behaviour.",
            "Review merchant and geographic behaviour.",
            "Review recent declines and payment velocity.",
            "Card-not-present status alone does not prove fraud.",
        ],
    },
    {
        "query_id": "q003",
        "question": ("What behavioural indicators can suggest account takeover?"),
        "expected_doc_id": "account_takeover_guide",
        "expected_facts": [
            "Abrupt changes in spending behaviour can be relevant.",
            "High transaction velocity can be relevant.",
            "New merchants or unusual countries can be relevant.",
            "Investigators should evaluate combinations of indicators.",
        ],
    },
    {
        "query_id": "q004",
        "question": ("How should an investigator assess a payment made to a high-risk merchant?"),
        "expected_doc_id": "merchant_risk_guide",
        "expected_facts": [
            "High-risk merchants deserve increased scrutiny.",
            "Merchant risk should be combined with other evidence.",
            "Merchant risk alone must not automatically classify fraud.",
        ],
    },
    {
        "query_id": "q005",
        "question": (
            "Can repeated Kafka deliveries with the same event_id be counted as separate customer payment attempts?"
        ),
        "expected_doc_id": "duplicate_payment_guide",
        "expected_facts": [
            "Duplicate event delivery is not automatically a duplicate payment.",
            "The same event_id represents the same logical event.",
            "Kafka retries or replay should not inflate customer behaviour.",
            "Investigators should compare event and delivery metadata.",
        ],
    },
    {
        "query_id": "q006",
        "question": ("How should a cross-border high-value payment be investigated?"),
        "expected_doc_id": "cross_border_guide",
        "expected_facts": [
            "Compare the payment with customer geographic history.",
            "Combine cross-border status with other risk indicators.",
            "Cross-border activity alone does not establish fraud.",
        ],
    },
    {
        "query_id": "q007",
        "question": ("Why could several declined transactions followed by an approved payment be suspicious?"),
        "expected_doc_id": "decline_pattern_guide",
        "expected_facts": [
            "Repeated declines can be associated with credential testing.",
            "Investigators should review timing and transaction values.",
            "Declines should be combined with other fraud evidence.",
        ],
    },
    {
        "query_id": "q008",
        "question": ("Should a high fraud-model probability be treated as proof that a payment is fraudulent?"),
        "expected_doc_id": "decision_standard_guide",
        "expected_facts": [
            "A model probability is an investigation aid.",
            "A model score must not be described as definitive proof.",
            "Investigators should use multiple independent signals.",
        ],
    },
    {
        "query_id": "q009",
        "question": (
            "What should investigators compare before deciding that "
            "two streaming records represent two customer payments?"
        ),
        "expected_doc_id": "duplicate_payment_guide",
        "expected_facts": [
            "Compare event_id.",
            "Compare transaction_id.",
            "Compare event timestamps and delivery metadata.",
        ],
    },
    {
        "query_id": "q010",
        "question": (
            "A customer normally pays domestically but suddenly makes "
            "an overseas ecommerce transaction. What should be reviewed?"
        ),
        "expected_doc_id": "cross_border_guide",
        "expected_facts": [
            "Compare current geography with historical customer behaviour.",
            "Review card-not-present status.",
            "Review other risk indicators such as velocity and merchant behaviour.",
        ],
    },
    {
        "query_id": "q011",
        "question": ("Why is looking at multiple fraud indicators better than making a decision from one feature?"),
        "expected_doc_id": "decision_standard_guide",
        "expected_facts": [
            "Fraud decisions should use multiple independent signals.",
            "Observed facts should be distinguished from hypotheses.",
            "Insufficient evidence should lead to further investigation.",
        ],
    },
    {
        "query_id": "q012",
        "question": (
            "A high-value online payment follows several failed attempts. "
            "What investigation pattern does this resemble?"
        ),
        "expected_doc_id": "account_takeover_guide",
        "expected_facts": [
            "Repeated attempts before a successful transaction can be relevant.",
            "High-value activity should be compared with historical behaviour.",
            "Multiple indicators should be considered together.",
        ],
    },
]


evaluation_rows = [
    {
        **case,
        "created_at": generated_at,
    }
    for case in EVALUATION_CASES
]


evaluation_df = spark_session.createDataFrame(evaluation_rows)


(
    evaluation_df.write.mode("overwrite")
    .option(
        "overwriteSchema",
        "true",
    )
    .saveAsTable(EVALUATION_TABLE)
)


# COMMAND ----------
# Validation.

knowledge_count = spark_session.table(KNOWLEDGE_TABLE).count()

evaluation_count = spark_session.table(EVALUATION_TABLE).count()


if knowledge_count < len(DOCUMENTS):
    raise RuntimeError("Knowledge-base generation produced fewer chunks than expected")


if evaluation_count != len(EVALUATION_CASES):
    raise RuntimeError("RAG evaluation dataset row count is incorrect")


print(f"Knowledge table: {KNOWLEDGE_TABLE}")

print(f"Knowledge chunks: {knowledge_count}")

print(f"Evaluation cases: {evaluation_count}")


display(
    spark_session.table(KNOWLEDGE_TABLE).orderBy(
        "doc_id",
        "chunk_ordinal",
    )
)


display(spark_session.table(EVALUATION_TABLE).orderBy("query_id"))
