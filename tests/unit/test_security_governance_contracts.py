from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ACCESS_MATRIX = ROOT / "governance" / "access-matrix.yml"

CLASSIFICATION = ROOT / "governance" / "classification.yml"

RBAC_SQL = ROOT / "sql" / "governance" / "16_apply_rbac.sql"

TAG_SQL = ROOT / "sql" / "governance" / "16_create_governed_tags.sql"

CLASSIFICATION_SQL = ROOT / "sql" / "governance" / "16_apply_data_classification.sql"

POLICY_SQL = ROOT / "sql" / "governance" / "16_create_abac_policies.sql"


def test_enterprise_security_groups_are_defined() -> None:
    source = ACCESS_MATRIX.read_text(encoding="utf-8")

    required_groups = [
        "epip-platform-admins",
        "epip-data-engineers",
        "epip-ml-engineers",
        "epip-fraud-analysts",
        "epip-bi-consumers",
    ]

    for group in required_groups:
        assert group in source


def test_ci_service_principal_is_not_production_role() -> None:
    source = ACCESS_MATRIX.read_text(encoding="utf-8")

    assert "epip-github-actions-ci" in source
    assert "production_access: prohibited" in source


def test_production_service_principal_is_not_dev_role() -> None:
    source = ACCESS_MATRIX.read_text(encoding="utf-8")

    assert "epip-github-actions-prod" in source
    assert "development_access: prohibited" in source


def test_governed_pii_tag_exists() -> None:
    source = TAG_SQL.read_text(encoding="utf-8")

    assert "CREATE GOVERNED TAG epip_pii" in source

    for value in [
        "name",
        "date_of_birth",
        "email",
        "phone",
        "address",
        "network_identifier",
    ]:
        assert value in source


def test_customer_pii_columns_are_classified() -> None:
    source = CLASSIFICATION_SQL.read_text(encoding="utf-8")

    required_columns = [
        "first_name",
        "last_name",
        "date_of_birth",
        "email",
        "phone",
        "address_line_1",
    ]

    for column in required_columns:
        assert column in source

    assert "'epip_classification' = 'restricted'" in source


def test_abac_masks_sensitive_columns() -> None:
    source = POLICY_SQL.read_text(encoding="utf-8")

    assert "COLUMN MASK" in source
    assert "has_tag_value('epip_pii'" in source

    assert "epip_mask_customer_email" in source
    assert "epip_mask_customer_phone" in source
    assert "epip_mask_customer_dob" in source


def test_abac_preserves_pipeline_identities() -> None:
    source = POLICY_SQL.read_text(encoding="utf-8")

    assert "`epip-github-actions-ci`" in source
    assert "`epip-github-actions-prod`" in source


def test_regional_row_filter_exists() -> None:
    source = POLICY_SQL.read_text(encoding="utf-8")

    assert "ROW FILTER" in source
    assert "epip_au_customer_scope" in source
    assert "epip-fraud-analysts-au" in source
