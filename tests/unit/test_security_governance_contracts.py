from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ACCESS_MATRIX = ROOT / "governance" / "access-matrix.yml"
CLASSIFICATION = ROOT / "governance" / "classification.yml"
RBAC_SQL = ROOT / "sql" / "governance" / "16_apply_rbac.sql"
TAG_SQL = ROOT / "sql" / "governance" / "16_create_governed_tags.sql"
CLASSIFICATION_SQL = ROOT / "sql" / "governance" / "16_apply_data_classification.sql"
FUNCTION_SQL = ROOT / "sql" / "governance" / "16_create_security_functions.sql"
POLICY_SQL = ROOT / "sql" / "governance" / "16_create_abac_policies.sql"
VALIDATION_SQL = ROOT / "sql" / "governance" / "16_validate_governance.sql"
README = ROOT / "README.md"
PROJECT_STATUS = ROOT / "docs" / "PROJECT_STATUS.md"
SECURITY_ARCHITECTURE = ROOT / "docs" / "architecture" / "security-governance.md"
M16_RUNBOOK = ROOT / "docs" / "demo" / "M16-runbook.md"


def test_enterprise_security_groups_are_defined() -> None:
    source = ACCESS_MATRIX.read_text(encoding="utf-8")
    for group in [
        "epip-platform-admins",
        "epip-data-engineers",
        "epip-ml-engineers",
        "epip-fraud-analysts",
        "epip-fraud-analysts-au",
        "epip-bi-consumers",
    ]:
        assert group in source


def test_human_access_uses_account_groups() -> None:
    source = ACCESS_MATRIX.read_text(encoding="utf-8")
    assert "human_access: account_groups" in source
    assert "workspace_group_source: account" in source
    assert "direct_user_grants: discouraged" in source


def test_service_principal_environment_isolation() -> None:
    source = ACCESS_MATRIX.read_text(encoding="utf-8")
    assert "epip-github-actions-ci" in source
    assert "production_access: prohibited" in source
    assert "epip-github-actions-prod" in source
    assert "development_access: prohibited" in source
    assert source.count("authentication: github_oidc") == 2


def test_all_governed_tags_are_declared() -> None:
    source = TAG_SQL.read_text(encoding="utf-8")
    assert "CREATE GOVERNED TAG epip_classification" in source
    assert "CREATE GOVERNED TAG epip_pii" in source
    assert "CREATE GOVERNED TAG epip_region_key" in source


def test_classification_contract_explains_enforcement_roles() -> None:
    source = CLASSIFICATION.read_text(encoding="utf-8")
    assert "epip_classification:" in source
    assert "epip_pii:" in source
    assert "epip_region_key:" in source
    assert "ABAC policy scope" in source
    assert "type-specific column masking" in source
    assert "jurisdictional row-level security" in source


def test_customer_table_is_restricted() -> None:
    source = CLASSIFICATION_SQL.read_text(encoding="utf-8")
    assert "payments_dev.silver.customers_current" in source
    assert "'epip_classification' = 'restricted'" in source


def test_customer_pii_columns_are_classified() -> None:
    source = CLASSIFICATION_SQL.read_text(encoding="utf-8")
    for column in [
        "first_name",
        "last_name",
        "date_of_birth",
        "email",
        "phone",
        "address_line_1",
        "city",
        "state",
        "postcode",
        "country",
    ]:
        assert f"ALTER COLUMN {column}" in source


def test_abac_uses_classification_as_policy_scope() -> None:
    source = POLICY_SQL.read_text(encoding="utf-8")
    condition = "WHEN has_tag_value('epip_classification', 'restricted')"
    assert source.count(condition) == 6


def test_abac_uses_pii_tag_for_mask_selection() -> None:
    source = POLICY_SQL.read_text(encoding="utf-8")
    for value in ["name", "email", "phone", "address", "date_of_birth"]:
        assert f"has_tag_value('epip_pii', '{value}')" in source


def test_abac_masks_sensitive_columns() -> None:
    source = POLICY_SQL.read_text(encoding="utf-8")
    for policy in [
        "epip_mask_customer_name",
        "epip_mask_customer_email",
        "epip_mask_customer_phone",
        "epip_mask_customer_address",
        "epip_mask_customer_dob",
    ]:
        assert policy in source


def test_automation_service_principals_are_not_mask_exceptions() -> None:
    source = POLICY_SQL.read_text(encoding="utf-8")
    assert "`epip-github-actions-ci`" not in source
    assert "`epip-github-actions-prod`" not in source


def test_regional_row_filter_exists() -> None:
    source = POLICY_SQL.read_text(encoding="utf-8")
    assert "epip_au_customer_scope" in source
    assert "`epip-fraud-analysts-au`" in source
    assert "has_tag_value('epip_region_key', 'country')" in source


def test_au_group_receives_explicit_base_rbac() -> None:
    source = RBAC_SQL.read_text(encoding="utf-8")
    assert source.count("`epip-fraud-analysts-au`") >= 7
    assert "ON TABLE payments_dev.silver.customers_current" in source


def test_security_functions_are_simple() -> None:
    source = FUNCTION_SQL.read_text(encoding="utf-8")
    for name in [
        "mask_string",
        "mask_email",
        "mask_date_of_birth",
        "allow_au_country",
    ]:
        assert name in source


def test_validation_checks_table_column_tags_and_effective_policies() -> None:
    source = VALIDATION_SQL.read_text(encoding="utf-8")
    assert "system.information_schema.table_tags" in source
    assert "system.information_schema.column_tags" in source
    assert "SHOW EFFECTIVE POLICIES" in source


def test_documentation_tracks_m16_as_in_progress() -> None:
    readme = README.read_text(encoding="utf-8")
    status = PROJECT_STATUS.read_text(encoding="utf-8")
    assert "Milestone 16 Security and Governance in progress" in readme
    assert "M16 | Security and governance | **IN PROGRESS**" in status


def test_security_documentation_exists() -> None:
    assert SECURITY_ARCHITECTURE.is_file()
    assert M16_RUNBOOK.is_file()
