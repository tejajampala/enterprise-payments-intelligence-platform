"""Contract tests for Milestone 14 analytics semantic assets."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

NOTEBOOK = ROOT / "notebooks" / "analytics" / "14_create_semantic_metrics.py"
BUNDLE_RESOURCE = ROOT / "bundle" / "resources" / "analytics_semantic_layer.yml"


def test_m14_notebook_is_databricks_source_notebook() -> None:
    """DAB must recognize the Python file as a Databricks source notebook."""

    first_line = NOTEBOOK.read_text(encoding="utf-8").splitlines()[0]

    assert first_line == "# Databricks notebook source"


def test_m14_creates_three_metric_views() -> None:
    """Dashboard and Genie must share all three semantic domains."""

    source = NOTEBOOK.read_text(encoding="utf-8")

    assert "payment_operations_metrics" in source
    assert "fraud_model_metrics" in source
    assert "agent_quality_metrics" in source

    assert source.count("WITH METRICS") == 3


def test_m14_metric_views_use_yaml_11() -> None:
    """Keep semantic definitions on the explicit YAML 1.1 contract."""

    source = NOTEBOOK.read_text(encoding="utf-8")

    assert source.count("version: 1.1") == 3


def test_m14_preserves_fraud_model_semantics() -> None:
    """Predicted fraud must remain a model signal, not confirmed fraud."""

    source = NOTEBOOK.read_text(encoding="utf-8")

    assert "predicted_fraud" in source
    assert "fraud_probability" in source
    assert "not a confirmed fraud outcome" in source


def test_m14_bundle_registers_analytics_schema_and_job() -> None:
    """The semantic layer must be reproducibly bundle-managed."""

    source = BUNDLE_RESOURCE.read_text(encoding="utf-8")

    assert "analytics_schema:" in source
    assert "analytics_semantic_layer_setup:" in source
    assert "14_create_semantic_metrics.py" in source
