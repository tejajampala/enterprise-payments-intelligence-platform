from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

MEDALLION_RESOURCE = ROOT / "bundle/resources/medallion_pipeline.yml"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _load_medallion_config() -> dict:
    with MEDALLION_RESOURCE.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_event_trust_pipeline_exists() -> None:
    assert (ROOT / "pipelines/silver/payment_event_trust.py").exists()


def test_event_watermark_is_configured() -> None:
    config = _load_medallion_config()

    silver = config["resources"]["pipelines"]["silver_transformations"]

    configuration = silver["configuration"]

    assert configuration["payments.streaming.eventWatermark"] == "6 hours"

    assert str(configuration["payments.streaming.lateThresholdSeconds"]) == "7200"


def test_trusted_events_use_streaming_input() -> None:
    source = _read("pipelines/silver/payment_event_trust.py")

    assert 'name="payment_events_trusted"' in source

    assert "spark.readStream" in source

    assert '"payment_events_validated"' in source


def test_trusted_events_use_event_time_order() -> None:
    source = _read("pipelines/silver/payment_event_trust.py")

    assert '"withEventTimeOrder"' in source

    assert '"true"' in source


def test_trusted_events_use_watermark() -> None:
    source = _read("pipelines/silver/payment_event_trust.py")

    assert ".withWatermark(" in source

    assert '"event_timestamp"' in source


def test_trusted_events_deduplicate_on_event_id() -> None:
    source = _read("pipelines/silver/payment_event_trust.py")

    assert ".dropDuplicatesWithinWatermark(" in source

    assert '["event_id"]' in source


def test_trusted_events_do_not_deduplicate_on_transaction_id() -> None:
    source = _read("pipelines/silver/payment_event_trust.py")

    assert '.dropDuplicatesWithinWatermark(\n            ["transaction_id"]' not in source


def test_exception_dataset_is_materialized_view() -> None:
    source = _read("pipelines/silver/payment_event_trust.py")

    assert "@dp.materialized_view" in source

    assert 'name="payment_event_exceptions"' in source


def test_exception_dataset_tracks_duplicate_late_and_ordering() -> None:
    source = _read("pipelines/silver/payment_event_trust.py")

    expected = [
        "is_duplicate_event",
        "is_late_arrival",
        "is_out_of_order",
        '"DUPLICATE"',
        '"LATE"',
        '"OUT_OF_ORDER"',
    ]

    for value in expected:
        assert value in source


def test_trusted_events_enable_change_tracking() -> None:
    source = _read("pipelines/silver/payment_event_trust.py")

    assert '"delta.enableRowTracking": "true"' in source

    assert '"delta.enableChangeDataFeed": "true"' in source
