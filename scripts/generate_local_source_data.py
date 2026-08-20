"""Generate reproducible local source-system datasets."""

import argparse
from pathlib import Path

from payments_intelligence.synthetic import (
    LocalSourceDatasetExporter,
    LocalSourceExportConfig,
    SyntheticDataConfig,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=("Generate deterministic local payments source-system datasets.")
    )

    parser.add_argument(
        "--output-root",
        default="data/generated/source_systems",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--customers",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--merchants",
        type=int,
        default=40,
    )

    parser.add_argument(
        "--transactions",
        type=int,
        default=1000,
    )

    args = parser.parse_args()

    synthetic_config = SyntheticDataConfig(
        seed=args.seed,
        customer_count=args.customers,
        merchant_count=args.merchants,
        transaction_count=args.transactions,
    )

    export_config = LocalSourceExportConfig(
        output_root=Path(args.output_root),
        synthetic=synthetic_config,
    )

    manifest = LocalSourceDatasetExporter(export_config).export()

    print(f"Source-system datasets written to: {manifest.root}")

    print("Record counts:")

    for name, count in sorted(manifest.counts.items()):
        print(f"  {name}: {count}")


if __name__ == "__main__":
    main()
