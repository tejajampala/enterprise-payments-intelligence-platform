-- Enterprise Payments Intelligence Platform
-- Milestone 3 / Step 3A
-- Historical payment transaction batch ingestion.

CREATE TABLE IF NOT EXISTS
  payments_dev.ingestion.payment_transactions_batch
(
    transaction_id STRING,
    account_id STRING,
    merchant_id STRING,

    event_timestamp TIMESTAMP,

    amount DECIMAL(18, 2),
    currency STRING,

    channel STRING,
    payment_method STRING,
    status STRING,

    card_present BOOLEAN,
    device_id STRING,
    ip_address STRING,
    country STRING,

    source_file STRING,
    source_file_name STRING,
    ingested_at TIMESTAMP
)
USING DELTA
COMMENT 'Raw batch-ingested historical payment transactions';


COPY INTO payments_dev.ingestion.payment_transactions_batch
FROM
(
    SELECT
        CAST(transaction_id AS STRING) AS transaction_id,
        CAST(account_id AS STRING) AS account_id,
        CAST(merchant_id AS STRING) AS merchant_id,

        CAST(event_timestamp AS TIMESTAMP) AS event_timestamp,

        CAST(amount AS DECIMAL(18, 2)) AS amount,
        CAST(currency AS STRING) AS currency,

        CAST(channel AS STRING) AS channel,
        CAST(payment_method AS STRING) AS payment_method,
        CAST(status AS STRING) AS status,

        CAST(card_present AS BOOLEAN) AS card_present,
        CAST(device_id AS STRING) AS device_id,
        CAST(ip_address AS STRING) AS ip_address,
        CAST(country AS STRING) AS country,

        _metadata.file_path AS source_file,
        _metadata.file_name AS source_file_name,

        current_timestamp() AS ingested_at

    FROM
      '/Volumes/payments_dev/landing/batch_source/historical_transactions/clean'
)
FILEFORMAT = JSON
FORMAT_OPTIONS (
    'recursiveFileLookup' = 'true'
);