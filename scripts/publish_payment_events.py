"""Publish deterministic synthetic payment events to Kafka."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from payments_intelligence.streaming import (
    ConfluentKafkaPublisher,
    DryRunKafkaPublisher,
    KafkaDataset,
    KafkaPublisher,
    ReplayConfig,
    replay_payment_events,
)

DEFAULT_SOURCE_ROOT = Path("data/generated/source_systems/seed-42/kafka/payment_events")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay deterministic payment events into Kafka.")

    parser.add_argument(
        "--source-root",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
    )

    parser.add_argument(
        "--dataset",
        choices=[dataset.value for dataset in KafkaDataset],
        default=KafkaDataset.CLEAN.value,
    )

    parser.add_argument(
        "--rate",
        type=float,
        default=0.0,
        help="Events per second. Use 0 to publish as fast as possible.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of records to publish.",
    )

    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS"),
    )

    parser.add_argument(
        "--client-id",
        default="payments-event-producer",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and replay records without connecting to Kafka.",
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    config = ReplayConfig(
        source_root=args.source_root,
        dataset=KafkaDataset(args.dataset),
        rate_per_second=args.rate,
        limit=args.limit,
    )

    publisher: KafkaPublisher

    if args.dry_run:
        publisher = DryRunKafkaPublisher()
        mode = "DRY_RUN"
    else:
        if not args.bootstrap_servers:
            parser.error(
                "--bootstrap-servers or KAFKA_BOOTSTRAP_SERVERS "
                "is required unless --dry-run is used"
            )

        publisher = ConfluentKafkaPublisher(
            bootstrap_servers=args.bootstrap_servers,
            client_id=args.client_id,
        )

        mode = "KAFKA"

    summary = replay_payment_events(
        config=config,
        publisher=publisher,
    )

    print(f"Mode: {mode}")
    print(f"Dataset: {config.dataset.value}")
    print(f"Records published: {summary.records_published}")
    print(f"Topic counts: {summary.topic_counts}")
    print(f"Scenario counts: {summary.scenario_counts}")
    print(f"First message key: {summary.first_message_key}")
    print(f"Last message key: {summary.last_message_key}")


if __name__ == "__main__":
    main()
