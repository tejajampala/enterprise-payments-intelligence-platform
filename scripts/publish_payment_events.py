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
    build_msk_iam_kafka_config,
    replay_payment_events,
)


DEFAULT_SOURCE_ROOT = Path(
    "data/generated/source_systems/seed-42/kafka/payment_events"
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay deterministic payment events into Kafka."
    )

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
        "--aws-msk-iam",
        action="store_true",
        help="Authenticate to Amazon MSK using AWS IAM.",
    )

    parser.add_argument(
        "--aws-region",
        default=(
            os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
        ),
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

        extra_config: dict[str, object] | None = None

        if args.aws_msk_iam:
            if not args.aws_region:
                parser.error(
                    "--aws-region, AWS_REGION, or AWS_DEFAULT_REGION "
                    "is required when --aws-msk-iam is used"
                )

            extra_config = (
                build_msk_iam_kafka_config(
                    args.aws_region
                )
            )

        publisher = ConfluentKafkaPublisher(
            bootstrap_servers=args.bootstrap_servers,
            client_id=args.client_id,
            extra_config=extra_config,
        )

        mode = (
            "AWS_MSK_IAM"
            if args.aws_msk_iam
            else "KAFKA"
        )

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