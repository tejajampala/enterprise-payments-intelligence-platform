provider "aws" {
  region = var.aws_region
}


data "aws_caller_identity" "current" {}


locals {
  project_name = "enterprise-payments-intelligence-platform"

  bucket_name = join(
    "-",
    [
      "epip",
      data.aws_caller_identity.current.account_id,
      var.aws_region
    ]
  )

  unity_catalog_role_name = "epip-${var.environment}-uc-s3-access"

  # Static Databricks Unity Catalog AWS principal documented by Databricks.
  unity_catalog_master_role_arn = "arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL"

  # ARN of the IAM role that this Terraform configuration creates.
  unity_catalog_role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.unity_catalog_role_name}"

  # Initial bootstrap:
  #   only the Databricks Unity Catalog master role is trusted.
  #
  # Final configuration:
  #   Databricks master role + this IAM role itself are trusted.
  assume_role_principals = (
    var.enable_databricks_role_self_assume
    ? [
      local.unity_catalog_master_role_arn,
      local.unity_catalog_role_arn
    ]
    : [
      local.unity_catalog_master_role_arn
    ]
  )

  landing_prefix = "payments/landing"

  common_tags = merge(
    {
      Project     = local.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Purpose     = "Databricks Unity Catalog external landing storage"
    },
    var.additional_tags
  )
}


# -------------------------------------------------------------------
# S3 landing bucket
# -------------------------------------------------------------------

resource "aws_s3_bucket" "payments_landing" {
  bucket = local.bucket_name

  # Protect landing data from accidental Terraform deletion.
  force_destroy = false

  tags = local.common_tags
}


resource "aws_s3_bucket_public_access_block" "payments_landing" {
  bucket = aws_s3_bucket.payments_landing.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


resource "aws_s3_bucket_ownership_controls" "payments_landing" {
  bucket = aws_s3_bucket.payments_landing.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}


resource "aws_s3_bucket_versioning" "payments_landing" {
  bucket = aws_s3_bucket.payments_landing.id

  versioning_configuration {
    status = "Enabled"
  }
}


resource "aws_s3_bucket_server_side_encryption_configuration" "payments_landing" {
  bucket = aws_s3_bucket.payments_landing.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}


resource "aws_s3_bucket_lifecycle_configuration" "payments_landing" {
  bucket = aws_s3_bucket.payments_landing.id

  rule {
    id     = "landing-storage-hygiene"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}


# Create the governed landing prefix during bootstrap.
resource "aws_s3_object" "landing_marker" {
  bucket  = aws_s3_bucket.payments_landing.id
  key     = "${local.landing_prefix}/.bootstrap"
  content = ""

  server_side_encryption = "AES256"

  tags = local.common_tags
}


# -------------------------------------------------------------------
# Unity Catalog IAM trust policy
# -------------------------------------------------------------------

data "aws_iam_policy_document" "unity_catalog_assume_role" {
  statement {
    sid    = "AllowDatabricksUnityCatalogAssumeRole"
    effect = "Allow"

    actions = [
      "sts:AssumeRole"
    ]

    principals {
      type        = "AWS"
      identifiers = local.assume_role_principals
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"

      values = [
        var.databricks_storage_credential_external_id
      ]
    }
  }
}


resource "aws_iam_role" "unity_catalog_s3_access" {
  name = local.unity_catalog_role_name

  description = "Unity Catalog access to the Enterprise Payments Intelligence Platform S3 landing zone."

  assume_role_policy = data.aws_iam_policy_document.unity_catalog_assume_role.json

  tags = local.common_tags
}


# -------------------------------------------------------------------
# Least-privilege S3 permissions
# -------------------------------------------------------------------

data "aws_iam_policy_document" "unity_catalog_s3_access" {

  statement {
    sid    = "ReadBucketMetadata"
    effect = "Allow"

    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucketMultipartUploads"
    ]

    resources = [
      aws_s3_bucket.payments_landing.arn
    ]
  }


  statement {
    sid    = "ListLandingPrefix"
    effect = "Allow"

    actions = [
      "s3:ListBucket"
    ]

    resources = [
      aws_s3_bucket.payments_landing.arn
    ]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"

      values = [
        local.landing_prefix,
        "${local.landing_prefix}/*"
      ]
    }
  }


  statement {
    sid    = "ReadWriteLandingObjects"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListMultipartUploadParts",
      "s3:AbortMultipartUpload"
    ]

    resources = [
      "${aws_s3_bucket.payments_landing.arn}/${local.landing_prefix}/*"
    ]
  }


  # Required by the Databricks self-assuming IAM-role pattern.
  statement {
    sid    = "AllowSelfAssume"
    effect = "Allow"

    actions = [
      "sts:AssumeRole"
    ]

    resources = [
      local.unity_catalog_role_arn
    ]
  }
}


resource "aws_iam_policy" "unity_catalog_s3_access" {
  name = "epip-${var.environment}-uc-s3-access"

  description = "Least-privilege S3 access for the Enterprise Payments Intelligence Platform."

  policy = data.aws_iam_policy_document.unity_catalog_s3_access.json

  tags = local.common_tags
}


resource "aws_iam_role_policy_attachment" "unity_catalog_s3_access" {
  role = aws_iam_role.unity_catalog_s3_access.name

  policy_arn = aws_iam_policy.unity_catalog_s3_access.arn
}