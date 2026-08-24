# Real-Time Payment Streaming Demo Runbook

## Purpose

This runbook explains how to reproduce the real-time streaming portion of the
Enterprise Payments Intelligence Platform.

The demonstration covers:

- deterministic synthetic payment-event generation
- Amazon MSK Provisioned
- AWS IAM authentication
- Python Kafka producer
- Unity Catalog service credentials
- Databricks Serverless
- Lakeflow Spark Declarative Pipelines
- Bronze streaming ingestion
- Kafka partition and offset lineage
- duplicate deliveries
- out-of-order events
- late events
- streaming checkpoint recovery
- physical-delivery reconciliation

The streaming architecture is:

```text
Synthetic Payment Generator
        |
        v
Local JSONL Event Dataset
        |
        v
Python Kafka Replay Producer
        |
        | SASL/OAUTHBEARER
        | AWS IAM
        v
Amazon MSK
payments.events.v1
        |
        | TLS + IAM
        v
Unity Catalog Service Credential
payments_msk_dev
        |
        v
Databricks Serverless
        |
        v
Lakeflow Declarative Pipeline
        |
        v
payments_dev.bronze.payment_events
```

---

# 1. Prerequisites

The following tools are required:

- Python 3.12
- uv
- Git
- Terraform
- AWS CLI
- Databricks CLI
- an AWS account
- a Databricks workspace on AWS

The development examples in this repository use:

```text
AWS region: ap-southeast-2
Databricks CLI profile: PAYMENTS_DEV
Catalog: payments_dev
Kafka topic: payments.events.v1
Service credential: payments_msk_dev
```

Do not commit:

- AWS credentials
- Databricks tokens
- Terraform state
- `terraform.tfvars`
- generated synthetic datasets

---

# 2. Prepare the Python environment

From the repository root:

```powershell
uv sync
```

Verify:

```powershell
uv run python --version
```

Expected:

```text
Python 3.12.x
```

Run the tests:

```powershell
uv run pytest -v
```

---

# 3. Generate the deterministic source datasets

Generate the complete synthetic source-system dataset:

```powershell
uv run python scripts/generate_local_source_data.py
```

The default seed is:

```text
42
```

Generated files are written under:

```text
data/generated/source_systems/seed-42/
```

The streaming source files are:

```text
data/generated/source_systems/seed-42/kafka/payment_events/
├── clean.jsonl
└── scenarios.jsonl
```

`clean.jsonl` contains normal payment-event deliveries.

`scenarios.jsonl` contains controlled streaming anomalies:

```text
NORMAL
DUPLICATE
OUT_OF_ORDER
LATE
```

The generated data is deterministic, so the same seed produces the same
business entities and event scenarios.

---

# 4. Understand the Kafka event contract

An exported source event resembles:

```json
{
  "topic": "payments.events.v1",
  "message_key": "txn-00000001",
  "simulated_arrival_at": "2026-07-05T03:27:00+00:00",
  "scenario": "NORMAL",
  "payload": {
    "event_id": "event-000000001",
    "event_type": "AUTHORIZED",
    "event_timestamp": "2026-07-05T03:26:55+00:00",
    "sequence_number": 1,
    "transaction": {
      "transaction_id": "txn-00000001",
      "account_id": "...",
      "merchant_id": "...",
      "amount": "...",
      "currency": "AUD"
    }
  }
}
```

The Kafka message key is:

```text
transaction_id
```

This keeps events for the same transaction eligible for placement on the same
Kafka partition.

---

# 5. Timestamp semantics

Four different timestamps are intentionally maintained.

| Field | Meaning |
|---|---|
| `event_timestamp` | Business-event time |
| `simulated_arrival_at` | Synthetic delivery time used for testing |
| `kafka_timestamp` | Actual time the record is physically published to Kafka |
| `ingested_at` | Time Databricks writes the record into Bronze |

Important:

The producer does **not** use `simulated_arrival_at` as the physical Kafka record
timestamp.

Historical synthetic timestamps can be older than Kafka retention. Setting an
old synthetic timestamp as the physical Kafka timestamp can cause Kafka to
consider the message eligible for retention cleanup shortly after it is
published.

The synthetic timestamp therefore stays inside the event payload while Kafka
assigns the real physical publish timestamp.

---

# 6. AWS authentication

Verify AWS CLI authentication:

```powershell
aws sts get-caller-identity
```

If the AWS login session has expired:

```powershell
aws login
```

Then verify again:

```powershell
aws sts get-caller-identity
```

The Python MSK IAM signer uses the normal AWS SDK credential chain.

The repository includes the AWS CRT dependency required when the AWS Login
credential provider is used.

Verify Python can load credentials:

```powershell
uv run python -c "import botocore.session; c=botocore.session.get_session().get_credentials(); print('Credentials loaded:', c is not None)"
```

Expected:

```text
Credentials loaded: True
```

---

# 7. Check whether Amazon MSK currently exists

Run:

```powershell
terraform -chdir=infra/terraform/aws state list |
  Select-String "aws_msk_cluster.payments_streaming"
```

If the cluster exists, continue to the next section.

If no cluster exists, use the recreation procedure below.

---

# 8. Recreate MSK after it has previously been destroyed

Amazon MSK public broker access cannot be enabled during the initial creation of
a Provisioned cluster.

Therefore recreation is deliberately performed in two stages.

## 8.1 Initial private creation

In:

```text
infra/terraform/aws/terraform.tfvars
```

set:

```hcl
enable_msk_public_access = false
```

Then:

```powershell
terraform -chdir=infra/terraform/aws plan
```

Review the plan carefully.

Then:

```powershell
terraform -chdir=infra/terraform/aws apply
```

Wait until the MSK state is:

```text
ACTIVE
```

Check:

```powershell
$MskClusterArn = terraform `
  -chdir=infra/terraform/aws `
  output -raw msk_cluster_arn

aws kafka describe-cluster-v2 `
  --cluster-arn $MskClusterArn `
  --query "ClusterInfo.{Name:ClusterName,State:State}" `
  --output table
```

Expected:

```text
ACTIVE
```

## 8.2 Enable public IAM brokers

Change:

```hcl
enable_msk_public_access = true
```

Then:

```powershell
terraform -chdir=infra/terraform/aws plan
```

The MSK cluster should be updated in place.

It must not be destroyed and recreated.

Apply:

```powershell
terraform -chdir=infra/terraform/aws apply
```

Then obtain the public IAM brokers:

```powershell
terraform `
  -chdir=infra/terraform/aws `
  output -raw msk_public_bootstrap_brokers_sasl_iam
```

The endpoints should use:

```text
:9198
```

---

# 9. Create the Kafka topic after recreating MSK

Get the cluster ARN:

```powershell
$MskClusterArn = terraform `
  -chdir=infra/terraform/aws `
  output -raw msk_cluster_arn
```

Check existing topics:

```powershell
aws kafka list-topics `
  --cluster-arn $MskClusterArn `
  --topic-name-filter "payments.events.v1"
```

If the topic does not exist:

```powershell
aws kafka create-topic `
  --cluster-arn $MskClusterArn `
  --topic-name "payments.events.v1" `
  --partition-count 3 `
  --replication-factor 2
```

Verify:

```powershell
aws kafka list-topics `
  --cluster-arn $MskClusterArn `
  --topic-name-filter "payments.events.v1"
```

Expected configuration:

```text
Topic: payments.events.v1
Partitions: 3
Replication factor: 2
```

---

# 10. Verify the Databricks service credential

The Databricks service credential is:

```text
payments_msk_dev
```

Check it:

```powershell
databricks credentials get-credential `
  payments_msk_dev `
  -p PAYMENTS_DEV
```

Validate:

```powershell
databricks credentials validate-credential `
  --credential-name payments_msk_dev `
  --purpose SERVICE `
  -p PAYMENTS_DEV
```

This credential allows Databricks Serverless to assume the dedicated AWS IAM
role used for MSK consumption.

No AWS access keys are placed inside Databricks.

---

# 11. Configure the local Kafka producer

Set the public broker endpoints:

```powershell
$env:KAFKA_BOOTSTRAP_SERVERS = terraform `
  -chdir=infra/terraform/aws `
  output -raw msk_public_bootstrap_brokers_sasl_iam
```

Verify:

```powershell
$env:KAFKA_BOOTSTRAP_SERVERS
```

Expected:

```text
...amazonaws.com:9198,...amazonaws.com:9198
```

The producer uses:

```text
SASL_SSL
+
OAUTHBEARER
+
AWS IAM
```

No Kafka username/password is stored in the repository.

---

# 12. Dry-run event generation

Before connecting to Kafka, validate the event dataset locally:

```powershell
uv run python scripts/publish_payment_events.py `
  --dataset clean `
  --limit 10 `
  --dry-run
```

This validates the event envelopes without publishing anything to MSK.

---

# 13. Publish clean payment events

Publish ten clean events:

```powershell
uv run python scripts/publish_payment_events.py `
  --dataset clean `
  --limit 10 `
  --aws-msk-iam `
  --aws-region ap-southeast-2
```

Expected output resembles:

```text
Mode: AWS_MSK_IAM
Dataset: clean
Records published: 10
Topic counts: {'payments.events.v1': 10}
Scenario counts: {'NORMAL': 10}
```

---

# 14. Verify Kafka directly from Databricks

Before involving Lakeflow, Kafka can be queried directly.

Replace `<PUBLIC_MSK_BROKERS>` with the current value returned by Terraform.

```sql
SELECT
    topic,
    partition,
    offset,
    timestamp AS kafka_timestamp,
    CAST(key AS STRING) AS kafka_key,
    CAST(value AS STRING) AS kafka_value
FROM read_kafka(
    bootstrapServers => '<PUBLIC_MSK_BROKERS>',
    subscribe => 'payments.events.v1',
    serviceCredential => 'payments_msk_dev',
    startingOffsets => 'earliest',
    endingOffsets => 'latest'
)
ORDER BY partition, offset;
```

Expected:

```text
rows > 0
```

The Kafka timestamps should represent the current physical publication time,
not the historical synthetic event time.

---

# 15. Configure Databricks bundle variables

Set MSK:

```powershell
$env:BUNDLE_VAR_msk_bootstrap_servers = terraform `
  -chdir=infra/terraform/aws `
  output -raw msk_public_bootstrap_brokers_sasl_iam
```

Set the existing S3 landing variable:

```powershell
$env:BUNDLE_VAR_s3_landing_url = terraform `
  -chdir=infra/terraform/aws `
  output -raw s3_landing_url
```

Optional explicit values:

```powershell
$env:BUNDLE_VAR_msk_topic = "payments.events.v1"
$env:BUNDLE_VAR_msk_service_credential_name = "payments_msk_dev"
```

---

# 16. Validate the Databricks bundle

```powershell
databricks bundle validate `
  -t dev `
  -p PAYMENTS_DEV
```

Expected:

```text
Validation OK
```

---

# 17. Deploy the Lakeflow pipeline

```powershell
databricks bundle deploy `
  -t dev `
  -p PAYMENTS_DEV
```

The streaming pipeline is:

```text
epip-dev-payment-events-bronze
```

The Bronze destination is:

```text
payments_dev.bronze.payment_events
```

---

# 18. Run the triggered Bronze pipeline

The pipeline intentionally uses triggered execution rather than continuous
execution.

Run:

```powershell
databricks bundle run `
  -t dev `
  -p PAYMENTS_DEV `
  payment_events_streaming
```

Flow:

```text
MSK
 |
 v
Lakeflow Serverless
 |
 v
Read available Kafka offsets
 |
 v
Write Bronze
 |
 v
Persist checkpoint
 |
 v
Stop
```

This avoids keeping Databricks streaming compute continuously active during
portfolio development.

---

# 19. Validate Bronze

Count records:

```sql
SELECT COUNT(*) AS bronze_records
FROM payments_dev.bronze.payment_events;
```

Inspect events:

```sql
SELECT
    event_id,
    transaction_id,
    event_type,
    amount,
    currency,
    delivery_scenario,
    event_timestamp,
    simulated_arrival_at,
    kafka_timestamp,
    ingested_at
FROM payments_dev.bronze.payment_events
ORDER BY ingested_at DESC
LIMIT 20;
```

---

# 20. Validate Kafka lineage

```sql
SELECT
    kafka_topic,
    kafka_partition,
    MIN(kafka_offset) AS min_offset,
    MAX(kafka_offset) AS max_offset,
    COUNT(*) AS physical_records
FROM payments_dev.bronze.payment_events
GROUP BY
    kafka_topic,
    kafka_partition
ORDER BY
    kafka_partition;
```

Bronze preserves:

```text
topic
partition
offset
Kafka timestamp
Kafka key
raw JSON
```

This allows a physical Kafka delivery to be traced independently from the
business event identity.

---

# 21. Publish the controlled streaming scenarios

The scenario dataset contains six physical deliveries:

```text
NORMAL        2
DUPLICATE     1
OUT_OF_ORDER  2
LATE          1
```

Publish:

```powershell
uv run python scripts/publish_payment_events.py `
  --dataset scenarios `
  --aws-msk-iam `
  --aws-region ap-southeast-2
```

Expected:

```text
Records published: 6
```

Then run the Bronze pipeline:

```powershell
databricks bundle run `
  -t dev `
  -p PAYMENTS_DEV `
  payment_events_streaming
```

---

# 22. Validate duplicate delivery

```sql
SELECT
    event_id,
    transaction_id,
    COUNT(*) AS physical_deliveries,
    collect_list(delivery_scenario) AS delivery_scenarios,
    collect_list(kafka_offset) AS kafka_offsets
FROM payments_dev.bronze.payment_events
WHERE event_id IN (
    SELECT event_id
    FROM payments_dev.bronze.payment_events
    WHERE delivery_scenario = 'DUPLICATE'
)
GROUP BY
    event_id,
    transaction_id;
```

The same business `event_id` should appear at multiple Kafka offsets.

Example:

```text
event-000000001
txn-00000001
physical_deliveries > 1
```

This is expected.

Bronze does not deduplicate physical source deliveries.

Deduplication belongs downstream in Silver.

---

# 23. Validate out-of-order delivery

```sql
SELECT
    transaction_id,
    event_id,
    sequence_number,
    event_timestamp,
    simulated_arrival_at,
    kafka_partition,
    kafka_offset,
    kafka_timestamp
FROM payments_dev.bronze.payment_events
WHERE delivery_scenario = 'OUT_OF_ORDER'
ORDER BY
    kafka_partition,
    kafka_offset;
```

The controlled scenario intentionally delivers:

```text
sequence 2
before
sequence 1
```

Bronze preserves source arrival behaviour rather than correcting it.

---

# 24. Validate the late-event scenario

```sql
SELECT
    transaction_id,
    event_id,
    event_timestamp,
    simulated_arrival_at,
    timestampdiff(
        HOUR,
        event_timestamp,
        simulated_arrival_at
    ) AS simulated_delay_hours,
    kafka_timestamp,
    ingested_at
FROM payments_dev.bronze.payment_events
WHERE delivery_scenario = 'LATE';
```

Expected:

```text
simulated_delay_hours = 4
```

---

# 25. Validate streaming checkpoint recovery

Record the current count:

```sql
SELECT COUNT(*) AS before_restart
FROM payments_dev.bronze.payment_events;
```

Publish nothing.

Run the pipeline again:

```powershell
databricks bundle run `
  -t dev `
  -p PAYMENTS_DEV `
  payment_events_streaming
```

Check:

```sql
SELECT COUNT(*) AS after_restart
FROM payments_dev.bronze.payment_events;
```

Expected:

```text
before_restart = after_restart
```

This proves the pipeline resumed using checkpointed Kafka offsets instead of
re-reading previously processed records.

---

# 26. Scenario summary

```sql
SELECT
    delivery_scenario,
    COUNT(*) AS physical_deliveries,
    COUNT(DISTINCT event_id) AS distinct_events
FROM payments_dev.bronze.payment_events
GROUP BY delivery_scenario
ORDER BY delivery_scenario;
```

This highlights the distinction between:

```text
physical Kafka deliveries
```

and:

```text
distinct business events
```

---

# 27. Full refresh during development

A full refresh should be used deliberately.

For the development pipeline:

```powershell
databricks bundle run `
  -t dev `
  -p PAYMENTS_DEV `
  payment_events_streaming `
  --full-refresh-all
```

A full refresh rebuilds the streaming table and resets the streaming state.

Do not use this casually in production.

---

# 28. Local quality checks

```powershell
uv run pytest -v
```

```powershell
uv run ruff check .
```

```powershell
uv run ruff format --check .
```

```powershell
uv run mypy src
```

Terraform:

```powershell
terraform -chdir=infra/terraform/aws fmt -recursive
terraform -chdir=infra/terraform/aws validate
```

Bundle:

```powershell
databricks bundle validate `
  -t dev `
  -p PAYMENTS_DEV
```

---

# 29. Cost management

Amazon MSK Provisioned incurs broker charges while the cluster is active, even
when no messages are being processed.

After the streaming demo has been completed and evidence has been captured,
remove the MSK cluster.

Do not run an unrestricted:

```powershell
terraform destroy
```

because the Terraform module also contains infrastructure used by other
milestones.

Instead destroy only the MSK cluster:

```powershell
terraform `
  -chdir=infra/terraform/aws `
  destroy `
  -target=aws_msk_cluster.payments_streaming
```

Review the plan carefully before entering:

```text
yes
```

The Bronze Delta data remains in Databricks after MSK is deleted and can be used
for later Medallion, data-quality, ML, and AI milestones.

Important:

Because the MSK resource still exists in Terraform source code, a later normal:

```powershell
terraform -chdir=infra/terraform/aws apply
```

will propose recreating the cluster.

Recreate it only when another streaming demonstration is required.

---

# 30. Recommended demo screenshots

Capture the following evidence for the portfolio:

1. Amazon MSK cluster in `ACTIVE` state.
2. `payments.events.v1` topic.
3. Databricks `payments_msk_dev` service credential.
4. Successful local producer output.
5. Lakeflow `epip-dev-payment-events-bronze` pipeline.
6. `payments_dev.bronze.payment_events` table.
7. Kafka partition/offset lineage query.
8. Duplicate-event query.
9. Out-of-order-event query.
10. Late-event query.
11. Checkpoint/restart record counts.

Do not include:

- AWS account IDs
- External IDs
- tokens
- secrets
- private credentials

---

# 31. Interview walkthrough

A concise explanation of the implementation is:

> I built a deterministic payments event generator and a replay producer that
> publishes events to Amazon MSK using AWS IAM authentication. The MSK topic is
> consumed by a Databricks Serverless Lakeflow pipeline using a Unity Catalog
> service credential, so no AWS keys are stored in Databricks. The Bronze layer
> preserves the raw JSON payload together with Kafka topic, partition, offset,
> key, and timestamp metadata. I deliberately generate duplicate, late, and
> out-of-order deliveries and preserve those physical source behaviours in
> Bronze. Downstream Silver processing is responsible for deduplication,
> sequencing, watermarking, and data-quality enforcement. Streaming checkpoints
> ensure pipeline restarts resume from previously committed Kafka offsets.

---

# 32. Troubleshooting

## Kafka returns zero rows shortly after publishing

Check the Kafka timestamp:

```sql
SELECT
    partition,
    offset,
    timestamp
FROM read_kafka(
    bootstrapServers => '<PUBLIC_MSK_BROKERS>',
    subscribe => 'payments.events.v1',
    serviceCredential => 'payments_msk_dev',
    startingOffsets => 'earliest',
    endingOffsets => 'latest'
);
```

The Kafka physical timestamp should be the current publication time.

Do not publish historical `simulated_arrival_at` as the Kafka physical record
timestamp because it can interact incorrectly with retention.

---

## `MissingDependencyException` mentioning `botocore[crt]`

Synchronize dependencies:

```powershell
uv sync
```

Verify AWS CRT:

```powershell
uv run python -c "import awscrt; print(awscrt.__version__)"
```

---

## MSK signer cannot load AWS credentials

Check:

```powershell
aws sts get-caller-identity
```

If necessary:

```powershell
aws login
```

---

## Kafka broker timeout

Verify:

- MSK is `ACTIVE`
- public IAM brokers exist
- brokers use port `9198`
- the security group allows the client source CIDR
- Databricks Serverless outbound CIDRs are allowed
- public access is enabled

---

## Databricks authentication error

Validate:

```powershell
databricks credentials validate-credential `
  --credential-name payments_msk_dev `
  --purpose SERVICE `
  -p PAYMENTS_DEV
```

---

## Bronze has zero rows but Kafka contains data

Run the triggered pipeline:

```powershell
databricks bundle run `
  -t dev `
  -p PAYMENTS_DEV `
  payment_events_streaming
```

If an old development checkpoint needs to be deliberately reset:

```powershell
databricks bundle run `
  -t dev `
  -p PAYMENTS_DEV `
  payment_events_streaming `
  --full-refresh-all
```

Use full refresh only when intentionally rebuilding the development stream.