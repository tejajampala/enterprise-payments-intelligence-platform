"""Repository contract tests for the Milestone 14 AI/BI dashboard."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESOURCE_DIR = ROOT / "bundle" / "resources"
ANALYTICS_DIR = ROOT / "src" / "analytics"


def _dashboard_resource_files() -> list[Path]:
    return sorted(RESOURCE_DIR.glob("*.dashboard.yml"))


def _dashboard_definition_files() -> list[Path]:
    return sorted(ANALYTICS_DIR.glob("*.lvdash.json"))


def test_m14_has_bundle_managed_dashboard_resource() -> None:
    resources = _dashboard_resource_files()

    assert resources, (
        "M14 requires a bundle-managed *.dashboard.yml resource. Generate and bind the working AI/BI dashboard first."
    )

    combined = "\n".join(path.read_text(encoding="utf-8") for path in resources)

    assert "dashboards:" in combined
    assert "EPIP Payments Intelligence" in combined


def test_m14_has_serialized_dashboard_definition() -> None:
    definitions = _dashboard_definition_files()

    assert definitions, "M14 requires a checked-in *.lvdash.json dashboard definition."

    for path in definitions:
        json.loads(path.read_text(encoding="utf-8"))


def test_epip_dashboard_contains_three_portfolio_pages() -> None:
    definitions = _dashboard_definition_files()
    combined = "\n".join(path.read_text(encoding="utf-8") for path in definitions)

    assert "Executive Payments" in combined
    assert "Fraud Intelligence" in combined
    assert "Fraud Agent Quality" in combined


def test_dashboard_does_not_query_bronze_directly() -> None:
    definitions = _dashboard_definition_files()
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in definitions)

    assert "payments_dev.bronze." not in combined


def test_dashboard_uses_governed_analytics_layer() -> None:
    definitions = _dashboard_definition_files()
    combined = "\n".join(path.read_text(encoding="utf-8") for path in definitions)

    assert "payments_dev.analytics." in combined
