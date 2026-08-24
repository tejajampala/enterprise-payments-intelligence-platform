# -------------------------------------------------------------------
# Databricks service credential IAM role for Amazon MSK
# -------------------------------------------------------------------
#
# This role is used by the Unity Catalog service credential:
#
#   payments_msk_dev
#
# It grants Databricks read-only Kafka consumer access to:
#
#   cluster: epip-dev-payments-streaming
#   topic:   payments.events.v1
#
# The role uses the Databricks Unity Catalog AWS master role as the
# initial trusted principal. After Databricks generates the real
# service-credential External ID, the role is updated to self-assume.
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

  # Convert:
  #
  # arn:aws:kafka:region:account:cluster/name/uuid
  #
  # into:
  #
  # arn:aws:kafka:region:account:topic/name/uuid/topic-name

  msk_databricks_topic_arn = (
    "${replace(
      aws_msk_cluster.payments_streaming.arn,
      ":cluster/",
      ":topic/"
    )}/${var.msk_topic_name}"
  )

  # Spark creates Kafka consumer groups for streaming queries.
  #
  # We restrict access to consumer groups belonging to this MSK
  # cluster rather than granting account-wide group access.

  msk_databricks_group_arn = (
    "${replace(
      aws_msk_cluster.payments_streaming.arn,
      ":cluster/",
      ":group/"
    )}/*"
  )
}


# -------------------------------------------------------------------
# Trust policy
# -------------------------------------------------------------------

data "aws_iam_policy_document" "msk_databricks_assume_role" {
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


resource "aws_iam_role" "msk_databricks" {
  name = local.msk_databricks_role_name

  description = (
    "Databricks Unity Catalog service credential access to Amazon MSK."
  )

  assume_role_policy = (
    data.aws_iam_policy_document.msk_databricks_assume_role.json
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
      aws_msk_cluster.payments_streaming.arn,
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
      local.msk_databricks_topic_arn,
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
      local.msk_databricks_group_arn,
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


resource "aws_iam_policy" "msk_databricks_access" {
  name = "epip-${var.environment}-msk-databricks-access"

  description = (
    "Least-privilege Amazon MSK consumer access for Databricks."
  )

  policy = (
    data.aws_iam_policy_document.msk_databricks_access.json
  )

  tags = local.common_tags
}


resource "aws_iam_role_policy_attachment" "msk_databricks_access" {
  role = aws_iam_role.msk_databricks.name

  policy_arn = aws_iam_policy.msk_databricks_access.arn
}