"""Kafka publishing and deterministic payment-event replay."""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol

from payments_intelligence.streaming.contracts import (
    KafkaEventEnvelope,
    KafkaRecord,
)


class KafkaDataset(StrEnum):
    """Generated Kafka datasets available for replay."""

    CLEAN = "clean"
    SCENARIOS = "scenarios"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class ReplayConfig:
    """Configuration controlling deterministic Kafka replay."""

    source_root: Path
    dataset: KafkaDataset = KafkaDataset.CLEAN
    rate_per_second: float = 0.0
    limit: int | None = None

    def __post_init__(self) -> None:
        if self.rate_per_second < 0:
            raise ValueError("rate_per_second must be >= 0")

        if self.limit is not None and self.limit <= 0:
            raise ValueError("limit must be greater than zero")


@dataclass(frozen=True, slots=True)
class ReplaySummary:
    """Summary returned after replay completes."""

    records_published: int
    topic_counts: dict[str, int]
    scenario_counts: dict[str, int]
    first_message_key: str | None
    last_message_key: str | None


class KafkaPublisher(Protocol):
    """Transport abstraction used by the replay engine."""

    def publish(self, record: KafkaRecord) -> None:
        """Publish one Kafka record."""

    def close(self) -> None:
        """Flush and release transport resources."""


class DryRunKafkaPublisher:
    """In-memory publisher used for validation without a Kafka cluster."""

    def __init__(self) -> None:
        self.records: list[KafkaRecord] = []
        self.closed = False

    def publish(self, record: KafkaRecord) -> None:
        if self.closed:
            raise RuntimeError("publisher is already closed")

        self.records.append(record)

    def close(self) -> None:
        self.closed = True


class ConfluentKafkaPublisher:
    """Kafka publisher backed by confluent-kafka."""

    def __init__(
        self,
        bootstrap_servers: str,
        client_id: str = "payments-event-producer",
        extra_config: Mapping[str, object] | None = None,
    ) -> None:
        if not bootstrap_servers.strip():
            raise ValueError("bootstrap_servers must not be empty")

        confluent_kafka = import_module("confluent_kafka")
        producer_type = confluent_kafka.Producer

        producer_config: dict[str, object] = {
            "bootstrap.servers": bootstrap_servers,
            "client.id": client_id,
            "enable.idempotence": True,
            "acks": "all",
        }

        if extra_config is not None:
            producer_config.update(extra_config)

        self._producer: Any = producer_type(producer_config)
        self._delivery_errors: list[str] = []
        self._closed = False

    def _delivery_report(
        self,
        error: Any,
        message: Any,
    ) -> None:
        if error is not None:
            self._delivery_errors.append(str(error))

    def publish(self, record: KafkaRecord) -> None:
        if self._closed:
            raise RuntimeError("publisher is already closed")

        for attempt in range(3):
            try:
                self._producer.produce(
                    topic=record.topic,
                    key=record.key,
                    value=record.value,
                    timestamp=record.timestamp_ms,
                    on_delivery=self._delivery_report,
                )
                self._producer.poll(0)
                return
            except BufferError:
                if attempt == 2:
                    raise

                self._producer.poll(1)

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        outstanding = self._producer.flush(30)

        if outstanding:
            raise RuntimeError(f"{outstanding} Kafka messages were not delivered")

        if self._delivery_errors:
            errors = "; ".join(self._delivery_errors)
            raise RuntimeError(f"Kafka delivery failures occurred: {errors}")


def _dataset_paths(
    source_root: Path,
    dataset: KafkaDataset,
) -> tuple[Path, ...]:
    clean = source_root / "clean.jsonl"
    scenarios = source_root / "scenarios.jsonl"

    paths: tuple[Path, ...]

    if dataset is KafkaDataset.CLEAN:
        paths = (clean,)
    elif dataset is KafkaDataset.SCENARIOS:
        paths = (scenarios,)
    else:
        paths = (
            clean,
            scenarios,
        )

    missing = [path for path in paths if not path.exists()]

    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Kafka replay source files do not exist: {missing_text}")

    return paths


def iter_event_envelopes(
    source_root: Path,
    dataset: KafkaDataset,
) -> Iterator[KafkaEventEnvelope]:
    """Yield validated source envelopes in deterministic file/line order."""

    for path in _dataset_paths(source_root, dataset):
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue

                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSON") from exc

                if not isinstance(raw, dict):
                    raise ValueError(f"{path}:{line_number}: Kafka envelope must be an object")

                try:
                    yield KafkaEventEnvelope.from_mapping(raw)
                except ValueError as exc:
                    raise ValueError(f"{path}:{line_number}: {exc}") from exc


def replay_payment_events(
    config: ReplayConfig,
    publisher: KafkaPublisher,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> ReplaySummary:
    """Replay generated payment events through the supplied publisher."""

    topic_counts: Counter[str] = Counter()
    scenario_counts: Counter[str] = Counter()

    published = 0
    first_message_key: str | None = None
    last_message_key: str | None = None

    interval = 1.0 / config.rate_per_second if config.rate_per_second > 0 else 0.0

    try:
        for envelope in iter_event_envelopes(
            config.source_root,
            config.dataset,
        ):
            if config.limit is not None and published >= config.limit:
                break

            publisher.publish(envelope.to_kafka_record())

            published += 1

            topic_counts[envelope.topic] += 1
            scenario_counts[envelope.scenario.value] += 1

            if first_message_key is None:
                first_message_key = envelope.message_key

            last_message_key = envelope.message_key

            if interval > 0:
                sleep_fn(interval)
    finally:
        publisher.close()

    return ReplaySummary(
        records_published=published,
        topic_counts=dict(sorted(topic_counts.items())),
        scenario_counts=dict(sorted(scenario_counts.items())),
        first_message_key=first_message_key,
        last_message_key=last_message_key,
    )
