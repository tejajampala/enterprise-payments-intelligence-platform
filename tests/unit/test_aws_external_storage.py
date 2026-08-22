"""Tests for the AWS S3 and Unity Catalog external-storage foundation."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
AWS_TERRAFORM = ROOT / "infra" / "terraform" / "aws"


def test_aws_terraform_files_exist() -> None:
    """The AWS infrastructure layer must contain the expected Terraform files."""

    required_files = (
        "versions.tf",
        "variables.tf",
        "main.tf",
        "outputs.tf",
        "terraform.tfvars.example",
    )

    for file_name in required_files:
        assert (AWS_TERRAFORM / file_name).exists()


def test_terraform_state_is_ignored() -> None:
    """Terraform state must never be committed to source control."""

    gitignore = (ROOT / ".gitignore").read_text(
        encoding="utf-8",
    )

    assert "*.tfstate" in gitignore
    assert "*.tfstate.*" in gitignore


def test_real_terraform_variables_are_ignored() -> None:
    """Environment-specific Terraform variables must remain local."""

    gitignore = (ROOT / ".gitignore").read_text(
        encoding="utf-8",
    )

    assert "*.tfvars" in gitignore
    assert "*.tfvars.json" in gitignore
    assert "!*.tfvars.example" in gitignore


def test_s3_bucket_blocks_public_access() -> None:
    """The landing bucket must explicitly block public access."""

    terraform = (AWS_TERRAFORM / "main.tf").read_text(
        encoding="utf-8",
    )

    assert 'resource "aws_s3_bucket_public_access_block"' in terraform

    assert "block_public_acls       = true" in terraform
    assert "block_public_policy     = true" in terraform
    assert "ignore_public_acls      = true" in terraform
    assert "restrict_public_buckets = true" in terraform


def test_s3_bucket_enforces_bucket_owner() -> None:
    """S3 ACL ownership should be disabled through BucketOwnerEnforced."""

    terraform = (AWS_TERRAFORM / "main.tf").read_text(
        encoding="utf-8",
    )

    assert 'object_ownership = "BucketOwnerEnforced"' in terraform


def test_s3_bucket_enables_versioning() -> None:
    """The external landing bucket must use S3 versioning."""

    terraform = (AWS_TERRAFORM / "main.tf").read_text(
        encoding="utf-8",
    )

    assert 'resource "aws_s3_bucket_versioning"' in terraform
    assert 'status = "Enabled"' in terraform


def test_s3_bucket_enables_encryption() -> None:
    """The landing bucket must enable server-side encryption."""

    terraform = (AWS_TERRAFORM / "main.tf").read_text(
        encoding="utf-8",
    )

    assert 'resource "aws_s3_bucket_server_side_encryption_configuration"' in terraform

    assert 'sse_algorithm = "AES256"' in terraform


def test_s3_bucket_does_not_force_destroy_data() -> None:
    """Terraform should not silently delete all landing data."""

    terraform = (AWS_TERRAFORM / "main.tf").read_text(
        encoding="utf-8",
    )

    assert "force_destroy = false" in terraform


def test_iam_trust_uses_external_id() -> None:
    """Unity Catalog role assumption must require the external ID."""

    terraform = (AWS_TERRAFORM / "main.tf").read_text(
        encoding="utf-8",
    )

    assert 'variable = "sts:ExternalId"' in terraform

    assert "var.databricks_storage_credential_external_id" in terraform


def test_iam_supports_final_self_assume_trust() -> None:
    """The final IAM trust policy must support Databricks self-assumption."""

    terraform = (AWS_TERRAFORM / "main.tf").read_text(
        encoding="utf-8",
    )

    assert "enable_databricks_role_self_assume" in terraform
    assert "local.unity_catalog_role_arn" in terraform


def test_external_location_bundle_resource_exists() -> None:
    """The governed S3 external location must be defined as bundle code."""

    assert (ROOT / "bundle" / "resources" / "aws_external_location.yml").exists()


def test_external_location_uses_storage_credential() -> None:
    """The external location must reference a Unity Catalog credential."""

    path = ROOT / "bundle" / "resources" / "aws_external_location.yml"

    with path.open(
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    location = config["resources"]["external_locations"]["payments_s3_landing"]

    assert location["name"] == "payments_s3_landing_dev"

    assert location["url"] == "${var.s3_landing_url}"

    assert location["credential_name"] == "${var.storage_credential_name}"


def test_external_location_file_events_are_disabled() -> None:
    """Batch ingestion should not introduce file-event infrastructure yet."""

    path = ROOT / "bundle" / "resources" / "aws_external_location.yml"

    with path.open(
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    location = config["resources"]["external_locations"]["payments_s3_landing"]

    assert location["enable_file_events"] is False
