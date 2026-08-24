"""Tests for the Milestone 4A Kafka streaming foundation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from payments_intelligence.streaming import (
    DryRunKafkaPublisher,
    KafkaDataset,
    KafkaEventEnvelope,
    ReplayConfig,
    iter_event_envelopes,
    replay_payment_events,
)


def _event_envelope(
    message_key: str = "TXN-001",
    scenario: str = "NORMAL",
) -> dict[str, object]:
    return {
        "topic": "payments.events.v1",
        "message_key": message_key,
        "simulated_arrival_at": "2026-08-01T10:00:05+00:00",
        "scenario": scenario,
        "payload": {
            "event_id": f"EVENT-{message_key}",
            "event_type": "PAYMENT_AUTHORISED",
            "event_timestamp": "2026-08-01T10:00:00+00:00",
            "sequence_number": 1,
            "transaction": {
                "transaction_id": message_key,
                "account_id": "ACC-001",
                "merchant_id": "MERCHANT-001",
                "event_timestamp": "2026-08-01T10:00:00+00:00",
                "amount": "42.50",
                "currency": "AUD",
                "channel": "ONLINE",
                "payment_method": "CARD",
                "status": "APPROVED",
                "card_present": False,
                "device_id": "DEVICE-001",
                "ip_address": "203.0.113.10",
                "country": "AU",
            },
        },
    }


def _write_jsonl(
    path: Path,
    records: list[dict[str, object]],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:
        for record in records:
            file.write(
                json.dumps(
                    record,
                    sort_keys=True,
                )
            )
            file.write("\n")


def _write_dataset(
    root: Path,
    clean: list[dict[str, object]],
    scenarios: list[dict[str, object]],
) -> None:
    _write_jsonl(
        root / "clean.jsonl",
        clean,
    )

    _write_jsonl(
        root / "scenarios.jsonl",
        scenarios,
    )


def test_envelope_creates_transport_record() -> None:
    envelope = KafkaEventEnvelope.from_mapping(_event_envelope())

    record = envelope.to_kafka_record()

    assert record.topic == "payments.events.v1"
    assert record.key == b"TXN-001"

    value = json.loads(record.value.decode("utf-8"))

    assert value["scenario"] == "NORMAL"
    assert value["payload"]["transaction"]["transaction_id"] == "TXN-001"

    assert "topic" not in value
    assert "message_key" not in value


def test_envelope_uses_simulated_arrival_as_kafka_timestamp() -> None:
    envelope = KafkaEventEnvelope.from_mapping(_event_envelope())

    record = envelope.to_kafka_record()

    assert record.timestamp_ms == 1785578405000


def test_envelope_rejects_unknown_scenario() -> None:
    raw = _event_envelope(scenario="UNKNOWN")

    with pytest.raises(
        ValueError,
        match="scenario must be one of",
    ):
        KafkaEventEnvelope.from_mapping(raw)


def test_envelope_rejects_timezone_naive_arrival() -> None:
    raw = _event_envelope()
    raw["simulated_arrival_at"] = "2026-08-01T10:00:05"

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        KafkaEventEnvelope.from_mapping(raw)


def test_envelope_rejects_missing_transaction_id() -> None:
    raw = _event_envelope()

    payload = raw["payload"]
    assert isinstance(payload, dict)

    transaction = payload["transaction"]
    assert isinstance(transaction, dict)

    del transaction["transaction_id"]

    with pytest.raises(
        ValueError,
        match="transaction_id",
    ):
        KafkaEventEnvelope.from_mapping(raw)


def test_clean_dataset_replay(tmp_path: Path) -> None:
    source_root = tmp_path / "payment_events"

    _write_dataset(
        source_root,
        clean=[
            _event_envelope("TXN-001"),
            _event_envelope("TXN-002"),
        ],
        scenarios=[
            _event_envelope(
                "TXN-003",
                scenario="DUPLICATE",
            )
        ],
    )

    publisher = DryRunKafkaPublisher()

    summary = replay_payment_events(
        ReplayConfig(
            source_root=source_root,
            dataset=KafkaDataset.CLEAN,
        ),
        publisher,
    )

    assert summary.records_published == 2
    assert summary.topic_counts == {"payments.events.v1": 2}
    assert summary.scenario_counts == {"NORMAL": 2}

    assert summary.first_message_key == "TXN-001"
    assert summary.last_message_key == "TXN-002"

    assert len(publisher.records) == 2
    assert publisher.closed is True


def test_all_dataset_preserves_file_order(tmp_path: Path) -> None:
    source_root = tmp_path / "payment_events"

    _write_dataset(
        source_root,
        clean=[
            _event_envelope("TXN-001"),
            _event_envelope("TXN-002"),
        ],
        scenarios=[
            _event_envelope(
                "TXN-003",
                scenario="LATE",
            ),
            _event_envelope(
                "TXN-004",
                scenario="OUT_OF_ORDER",
            ),
        ],
    )

    envelopes = list(
        iter_event_envelopes(
            source_root,
            KafkaDataset.ALL,
        )
    )

    assert [envelope.message_key for envelope in envelopes] == [
        "TXN-001",
        "TXN-002",
        "TXN-003",
        "TXN-004",
    ]


def test_replay_limit(tmp_path: Path) -> None:
    source_root = tmp_path / "payment_events"

    _write_dataset(
        source_root,
        clean=[
            _event_envelope("TXN-001"),
            _event_envelope("TXN-002"),
            _event_envelope("TXN-003"),
        ],
        scenarios=[],
    )

    publisher = DryRunKafkaPublisher()

    summary = replay_payment_events(
        ReplayConfig(
            source_root=source_root,
            dataset=KafkaDataset.CLEAN,
            limit=2,
        ),
        publisher,
    )

    assert summary.records_published == 2
    assert len(publisher.records) == 2


def test_replay_rate_controls_sleep_interval(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "payment_events"

    _write_dataset(
        source_root,
        clean=[
            _event_envelope("TXN-001"),
            _event_envelope("TXN-002"),
        ],
        scenarios=[],
    )

    sleep_calls: list[float] = []

    publisher = DryRunKafkaPublisher()

    replay_payment_events(
        ReplayConfig(
            source_root=source_root,
            dataset=KafkaDataset.CLEAN,
            rate_per_second=2.0,
        ),
        publisher,
        sleep_fn=sleep_calls.append,
    )

    assert sleep_calls == [
        0.5,
        0.5,
    ]


def test_invalid_json_reports_file_and_line(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "payment_events"

    clean_path = source_root / "clean.jsonl"

    clean_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    clean_path.write_text(
        "{invalid json}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="invalid JSON",
    ):
        list(
            iter_event_envelopes(
                source_root,
                KafkaDataset.CLEAN,
            )
        )
