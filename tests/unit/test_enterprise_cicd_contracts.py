"""Contract tests for Milestone 15A enterprise CI foundations."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
DATABRICKS_WORKFLOW = ROOT / ".github" / "workflows" / "databricks-ci.yml"
BUNDLE_TARGETS = ROOT / "bundle.targets.yml"


def test_python_ci_retains_core_quality_gates() -> None:
    source = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "uv run pytest -v" in source
    assert "uv run ruff check ." in source
    assert "uv run ruff format --check ." in source
    assert "uv run mypy src" in source
    assert "uv build" in source


def test_ci_validates_terraform_without_applying() -> None:
    source = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "terraform fmt -check -recursive" in source
    assert "terraform init -backend=false -input=false" in source
    assert "terraform validate" in source

    assert "terraform apply" not in source
    assert "terraform destroy" not in source


def test_databricks_ci_uses_github_oidc() -> None:
    source = DATABRICKS_WORKFLOW.read_text(encoding="utf-8")

    assert "id-token: write" in source
    assert "DATABRICKS_AUTH_TYPE: github-oidc" in source
    assert "DATABRICKS_HOST: ${{ vars.DATABRICKS_HOST }}" in source
    assert "DATABRICKS_CLIENT_ID: ${{ vars.DATABRICKS_CLIENT_ID }}" in source

    assert "DATABRICKS_TOKEN" not in source
    assert "DATABRICKS_CLIENT_SECRET" not in source


def test_databricks_pr_gate_is_validate_and_plan_only() -> None:
    source = DATABRICKS_WORKFLOW.read_text(encoding="utf-8")

    assert "databricks bundle validate -t ci" in source
    assert "databricks bundle plan -t ci" in source
    assert "databricks bundle deploy" not in source


def test_ci_bundle_target_is_isolated_and_safe() -> None:
    source = BUNDLE_TARGETS.read_text(encoding="utf-8")

    assert "ci:" in source
    assert 'name_prefix: "[ci ${workspace.current_user.short_name}] "' in source
    assert "trigger_pause_status: PAUSED" in source
    assert "pipelines_development: true" in source
    assert "jobs_max_concurrent_runs: 1" in source
