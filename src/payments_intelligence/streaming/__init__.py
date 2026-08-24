"""Streaming ingestion utilities for the payments platform."""

from payments_intelligence.streaming.contracts import (
    KafkaEventEnvelope,
    KafkaRecord,
)
from payments_intelligence.streaming.kafka_producer import (
    ConfluentKafkaPublisher,
    DryRunKafkaPublisher,
    KafkaDataset,
    KafkaPublisher,
    ReplayConfig,
    ReplaySummary,
    iter_event_envelopes,
    replay_payment_events,
)
from payments_intelligence.streaming.msk_auth import (
    build_msk_iam_kafka_config,
)

__all__ = [
    "ConfluentKafkaPublisher",
    "DryRunKafkaPublisher",
    "KafkaDataset",
    "KafkaEventEnvelope",
    "KafkaPublisher",
    "KafkaRecord",
    "ReplayConfig",
    "ReplaySummary",
    "build_msk_iam_kafka_config",
    "iter_event_envelopes",
    "replay_payment_events",
]
