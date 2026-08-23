"""Kafka transport contracts for payment-event streaming."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from payments_intelligence.synthetic.scenarios import DeliveryScenario

EVENT_REQUIRED_FIELDS = frozenset(
    {
        "event_id",
        "event_type",
        "event_timestamp",
        "sequence_number",
        "transaction",
    }
)

TRANSACTION_REQUIRED_FIELDS = frozenset(
    {
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
    }
)


def _required_string(
    source: Mapping[str, object],
    field_name: str,
) -> str:
    value = source.get(field_name)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")

    return value


def _required_mapping(
    source: Mapping[str, object],
    field_name: str,
) -> Mapping[str, object]:
    value = source.get(field_name)

    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")

    return value


def _required_aware_datetime(
    source: Mapping[str, object],
    field_name: str,
) -> datetime:
    text = _required_string(source, field_name)

    try:
        value = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 datetime") from exc

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")

    return value


def _validate_required_fields(
    source: Mapping[str, object],
    required_fields: frozenset[str],
    object_name: str,
) -> None:
    missing = sorted(required_fields.difference(source.keys()))

    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"{object_name} is missing required fields: {missing_text}")


@dataclass(frozen=True, slots=True)
class KafkaRecord:
    """Transport-ready Kafka record."""

    topic: str
    key: bytes
    value: bytes
    timestamp_ms: int


@dataclass(frozen=True, slots=True)
class KafkaEventEnvelope:
    """Validated source envelope used to create one Kafka record."""

    topic: str
    message_key: str
    simulated_arrival_at: datetime
    scenario: DeliveryScenario
    payload: dict[str, object]

    @classmethod
    def from_mapping(
        cls,
        source: Mapping[str, object],
    ) -> KafkaEventEnvelope:
        """Validate and construct a Kafka event envelope."""

        topic = _required_string(source, "topic")
        message_key = _required_string(source, "message_key")
        simulated_arrival_at = _required_aware_datetime(
            source,
            "simulated_arrival_at",
        )

        scenario_text = _required_string(source, "scenario")

        try:
            scenario = DeliveryScenario(scenario_text)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in DeliveryScenario)
            raise ValueError(f"scenario must be one of: {allowed}") from exc

        payload = _required_mapping(source, "payload")

        _validate_required_fields(
            payload,
            EVENT_REQUIRED_FIELDS,
            "payload",
        )

        _required_string(payload, "event_id")
        _required_string(payload, "event_type")
        _required_aware_datetime(payload, "event_timestamp")

        sequence_number = payload.get("sequence_number")

        if not isinstance(sequence_number, int) or isinstance(
            sequence_number,
            bool,
        ):
            raise ValueError("payload.sequence_number must be an integer")

        transaction = _required_mapping(payload, "transaction")

        _validate_required_fields(
            transaction,
            TRANSACTION_REQUIRED_FIELDS,
            "payload.transaction",
        )

        _required_string(transaction, "transaction_id")
        _required_string(transaction, "account_id")
        _required_string(transaction, "merchant_id")
        _required_aware_datetime(transaction, "event_timestamp")

        return cls(
            topic=topic,
            message_key=message_key,
            simulated_arrival_at=simulated_arrival_at,
            scenario=scenario,
            payload=dict(payload),
        )

    def to_kafka_record(self) -> KafkaRecord:
        """Convert the validated envelope into Kafka transport data."""

        kafka_value = {
            "simulated_arrival_at": self.simulated_arrival_at.isoformat(),
            "scenario": self.scenario.value,
            "payload": self.payload,
        }

        value = json.dumps(
            kafka_value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        timestamp_ms = int(self.simulated_arrival_at.timestamp() * 1000)

        return KafkaRecord(
            topic=self.topic,
            key=self.message_key.encode("utf-8"),
            value=value,
            timestamp_ms=timestamp_ms,
        )
