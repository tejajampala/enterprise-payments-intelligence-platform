"""Contract tests for Milestone 15A enterprise CI foundations."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
DATABRICKS_WORKFLOW = ROOT / ".github" / "workflows" / "databricks-ci.yml"
BUNDLE_TARGETS = ROOT / "bundle.targets.yml"
DATABRICKS_DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "databricks-deploy.yml"
PROMOTION_WORKFLOW = ROOT / ".github" / "workflows" / "promotion-gates.yml"
PROMOTION_RESOURCE = ROOT / "bundle" / "resources" / "promotion_gates.yml"
PRODUCTION_RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "production-release.yml"

PRODUCTION_BUNDLE = ROOT / "deploy" / "prod" / "databricks.yml"


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
    assert "DATABRICKS_TOKEN_AUDIENCE: ${{ vars.DATABRICKS_ACCOUNT_ID }}" in source

    assert "BUNDLE_VAR_msk_bootstrap_servers: ${{ secrets.MSK_BOOTSTRAP_SERVERS }}" in source

    assert "BUNDLE_VAR_s3_landing_url: ${{ secrets.S3_LANDING_URL }}" in source

    # CI must use GitHub OIDC, not stored Databricks credentials.
    assert "DATABRICKS_TOKEN:" not in source
    assert "secrets.DATABRICKS_TOKEN" not in source

    assert "DATABRICKS_CLIENT_SECRET:" not in source
    assert "secrets.DATABRICKS_CLIENT_SECRET" not in source


def test_databricks_pr_gate_is_validate_and_plan_only() -> None:
    source = DATABRICKS_WORKFLOW.read_text(encoding="utf-8")

    assert "databricks bundle validate -t ci" in source
    assert "databricks bundle plan -t ci" in source

    assert "--select" in source
    assert "pipelines.payment_events_streaming" in source
    assert "pipelines.silver_transformations" in source
    assert "pipelines.gold_analytics" in source

    assert "databricks bundle deploy" not in source


def test_ci_bundle_target_is_isolated_and_safe() -> None:
    source = BUNDLE_TARGETS.read_text(encoding="utf-8")

    assert "ci:" in source
    assert 'name_prefix: "[ci ${workspace.current_user.short_name}] "' in source
    assert "trigger_pause_status: PAUSED" in source
    assert "pipelines_development: true" in source
    assert "jobs_max_concurrent_runs: 1" in source


def test_pr_databricks_workflow_never_deploys() -> None:
    source = DATABRICKS_WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in source
    assert "databricks bundle validate -t ci" in source
    assert "databricks bundle plan -t ci" in source

    assert "databricks bundle deploy" not in source


def test_databricks_deployment_runs_only_after_main_merge() -> None:
    source = DATABRICKS_DEPLOY_WORKFLOW.read_text(encoding="utf-8")

    assert "push:" in source
    assert "- main" in source

    assert "pull_request:" not in source

    assert "environment: ci" in source
    assert "id-token: write" in source

    assert "DATABRICKS_AUTH_TYPE: github-oidc" in source
    assert "DATABRICKS_CLIENT_ID: ${{ vars.DATABRICKS_CLIENT_ID }}" in source
    assert "DATABRICKS_TOKEN_AUDIENCE: ${{ vars.DATABRICKS_ACCOUNT_ID }}" in source

    assert "databricks bundle validate -t ci" in source
    assert "databricks bundle plan -t ci" in source
    assert "databricks bundle deploy -t ci" in source
    assert "databricks bundle summary -t ci" in source

    assert "--select" in source
    assert "pipelines.payment_events_streaming" in source
    assert "pipelines.silver_transformations" in source
    assert "pipelines.gold_analytics" in source

    assert "DATABRICKS_TOKEN:" not in source
    assert "DATABRICKS_CLIENT_SECRET:" not in source


def test_ci_uses_isolated_catalog() -> None:
    source = BUNDLE_TARGETS.read_text(encoding="utf-8")

    assert "ci:" in source
    assert "catalog_name: payments_ci" in source


def test_controlled_deployment_includes_promotion_job() -> None:
    source = DATABRICKS_DEPLOY_WORKFLOW.read_text(encoding="utf-8")

    assert "jobs.promotion_quality_gates" in source


def test_promotion_gates_run_after_successful_deployment() -> None:
    source = PROMOTION_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_run:" in source
    assert "Databricks Controlled Deployment" in source
    assert "completed" in source

    assert "github.event.workflow_run.conclusion == 'success'" in source

    assert "environment: ci" in source
    assert "id-token: write" in source

    assert "DATABRICKS_AUTH_TYPE: github-oidc" in source

    assert "databricks bundle run -t ci promotion_quality_gates" in source

    assert "DATABRICKS_TOKEN:" not in source
    assert "DATABRICKS_CLIENT_SECRET:" not in source


def test_promotion_job_contains_ml_and_agent_gates() -> None:
    source = PROMOTION_RESOURCE.read_text(encoding="utf-8")

    assert "promotion_quality_gates:" in source

    assert "task_key: validate_fraud_model" in source
    assert "task_key: validate_agent_evaluation" in source

    assert "notebooks/promotion/15_validate_fraud_model.py" in source

    assert "notebooks/promotion/15_validate_agent_evaluation.py" in source


def test_agent_promotion_gate_requires_fresh_evidence() -> None:
    source = (ROOT / "notebooks" / "promotion" / "15_validate_agent_evaluation.py").read_text(encoding="utf-8")

    assert "evidence_is_fresh" in source
    assert "EPIP_AGENT_PROMOTION_GATE=PASS" in source
    assert "EPIP_AGENT_PROMOTION_GATE=FAIL" in source


def test_ml_promotion_gate_checks_champion() -> None:
    source = (ROOT / "notebooks" / "promotion" / "15_validate_fraud_model.py").read_text(encoding="utf-8")

    assert "Champion" in source
    assert "champion_matches_selected_model" in source
    assert "EPIP_ML_PROMOTION_GATE=PASS" in source
    assert "EPIP_ML_PROMOTION_GATE=FAIL" in source


def test_production_release_requires_successful_promotion() -> None:
    source = PRODUCTION_RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_run:" in source
    assert "EPIP Promotion Gates" in source

    assert "github.event.workflow_run.conclusion == 'success'" in source

    assert "environment: production" in source

    # Production must not be directly bypassable.
    assert "workflow_dispatch:" not in source
    assert "pull_request:" not in source


def test_production_release_uses_oidc() -> None:
    source = PRODUCTION_RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "id-token: write" in source

    assert "DATABRICKS_AUTH_TYPE: github-oidc" in source

    assert "DATABRICKS_CLIENT_ID: ${{ vars.DATABRICKS_CLIENT_ID }}" in source

    assert "DATABRICKS_TOKEN_AUDIENCE: ${{ vars.DATABRICKS_ACCOUNT_ID }}" in source

    assert "DATABRICKS_TOKEN:" not in source
    assert "DATABRICKS_CLIENT_SECRET:" not in source


def test_production_release_verifies_promoted_sha() -> None:
    source = PRODUCTION_RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "github.event.workflow_run.head_sha" in source
    assert "Verify promoted revision is current main" in source

    assert 'CURRENT_SHA="$(git rev-parse HEAD)"' in source

    assert 'test "${CURRENT_SHA}" = "${RELEASE_SHA}"' in source


def test_production_uses_full_bundle_deployment() -> None:
    source = PRODUCTION_RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "databricks bundle validate -t prod" in source
    assert "databricks bundle plan -t prod" in source

    assert "databricks bundle deploy" in source
    assert "-t prod" in source

    # Selective deployment is intentionally development-only.
    assert "--select" not in source


def test_production_bundle_is_production_mode() -> None:
    source = PRODUCTION_BUNDLE.read_text(encoding="utf-8")

    assert "mode: production" in source

    assert "root_path: /Workspace/Production/EPIP/.bundle/${bundle.name}/${bundle.target}" in source

    assert "service_principal_name: ${var.prod_service_principal_name}" in source


def test_production_pipelines_disable_development_mode() -> None:
    source = PRODUCTION_BUNDLE.read_text(encoding="utf-8")

    assert source.count("development: false") == 4

    assert "payment_events_streaming:" in source
    assert "silver_transformations:" in source
    assert "gold_analytics:" in source


def test_production_bundle_is_cost_safe() -> None:
    source = PRODUCTION_BUNDLE.read_text(encoding="utf-8")

    assert "catalog_name: payments_prod" not in source
    assert "default: payments_prod" in source

    # Expensive/global resources stay outside the initial production bundle.
    assert "vector_search_endpoints:" not in source
    assert "external_locations:" not in source
    assert "volumes:" not in source

    assert "continuous: true" not in source
