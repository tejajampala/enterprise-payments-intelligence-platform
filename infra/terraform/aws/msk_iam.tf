# -------------------------------------------------------------------
# Optional Databricks service-credential IAM role for Amazon MSK
# -------------------------------------------------------------------
#
# These resources exist only when:
#
#   enable_msk = true
#
# The IAM role is used by the Databricks Unity Catalog service
# credential for Kafka/MSK access.
#
# No MSK IAM role or policy remains provisioned while MSK is disabled.
# -------------------------------------------------------------------


locals {
  msk_databricks_role_name = (
    "epip-${var.environment}-msk-databricks"
  )

  msk_databricks_role_arn = (
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.msk_databricks_role_name}"
  )

  msk_databricks_assume_role_principals = (
    var.enable_databricks_msk_role_self_assume
    ? [
      local.unity_catalog_master_role_arn,
      local.msk_databricks_role_arn,
    ]
    : [
      local.unity_catalog_master_role_arn,
    ]
  )
}


# -------------------------------------------------------------------
# MSK Databricks role trust policy
# -------------------------------------------------------------------

data "aws_iam_policy_document" "msk_databricks_assume_role" {
  count = var.enable_msk ? 1 : 0

  statement {
    sid    = "AllowDatabricksUnityCatalogAssumeRole"
    effect = "Allow"

    actions = [
      "sts:AssumeRole",
    ]

    principals {
      type = "AWS"

      identifiers = (
        local.msk_databricks_assume_role_principals
      )
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"

      values = [
        var.databricks_msk_service_credential_external_id,
      ]
    }
  }
}


# -------------------------------------------------------------------
# Databricks MSK IAM role
# -------------------------------------------------------------------

resource "aws_iam_role" "msk_databricks" {
  count = var.enable_msk ? 1 : 0

  name = local.msk_databricks_role_name

  description = (
    "Databricks Unity Catalog service credential access to Amazon MSK."
  )

  assume_role_policy = (
    data.aws_iam_policy_document.msk_databricks_assume_role[0].json
  )

  tags = merge(
    local.common_tags,
    {
      Name    = local.msk_databricks_role_name
      Purpose = "Databricks Amazon MSK streaming access"
    }
  )
}


# -------------------------------------------------------------------
# Least-privilege MSK permissions
# -------------------------------------------------------------------

data "aws_iam_policy_document" "msk_databricks_access" {
  count = var.enable_msk ? 1 : 0


  # ---------------------------------------------------------------
  # Cluster connection
  # ---------------------------------------------------------------

  statement {
    sid    = "ConnectToPaymentsMSKCluster"
    effect = "Allow"

    actions = [
      "kafka-cluster:Connect",
      "kafka-cluster:DescribeCluster",
    ]

    resources = [
      aws_msk_cluster.payments_streaming[0].arn,
    ]
  }


  # ---------------------------------------------------------------
  # Topic read permissions
  # ---------------------------------------------------------------

  statement {
    sid    = "ReadPaymentEventsTopic"
    effect = "Allow"

    actions = [
      "kafka-cluster:DescribeTopic",
      "kafka-cluster:ReadData",
    ]

    resources = [
      "${replace(
        aws_msk_cluster.payments_streaming[0].arn,
        ":cluster/",
        ":topic/"
      )}/${var.msk_topic_name}",
    ]
  }


  # ---------------------------------------------------------------
  # Kafka consumer-group permissions
  # ---------------------------------------------------------------

  statement {
    sid    = "UseKafkaConsumerGroups"
    effect = "Allow"

    actions = [
      "kafka-cluster:DescribeGroup",
      "kafka-cluster:AlterGroup",
    ]

    resources = [
      "${replace(
        aws_msk_cluster.payments_streaming[0].arn,
        ":cluster/",
        ":group/"
      )}/*",
    ]
  }


  # ---------------------------------------------------------------
  # Required for Databricks service-credential self assumption
  # ---------------------------------------------------------------

  statement {
    sid    = "AllowSelfAssume"
    effect = "Allow"

    actions = [
      "sts:AssumeRole",
    ]

    resources = [
      local.msk_databricks_role_arn,
    ]
  }
}


# -------------------------------------------------------------------
# IAM policy
# -------------------------------------------------------------------

resource "aws_iam_policy" "msk_databricks_access" {
  count = var.enable_msk ? 1 : 0

  name = "epip-${var.environment}-msk-databricks-access"

  description = (
    "Least-privilege Amazon MSK consumer access for Databricks."
  )

  policy = (
    data.aws_iam_policy_document.msk_databricks_access[0].json
  )

  tags = local.common_tags
}


# -------------------------------------------------------------------
# IAM role -> policy attachment
# -------------------------------------------------------------------

resource "aws_iam_role_policy_attachment" "msk_databricks_access" {
  count = var.enable_msk ? 1 : 0

  role = aws_iam_role.msk_databricks[0].name

  policy_arn = aws_iam_policy.msk_databricks_access[0].arn
}