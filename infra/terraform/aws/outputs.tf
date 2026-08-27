# ===================================================================
# Persistent AWS / Unity Catalog outputs
# ===================================================================

output "aws_account_id" {
  description = "AWS account containing the payments landing zone."
  value       = data.aws_caller_identity.current.account_id
}


output "aws_region" {
  description = "AWS region containing the payments landing zone."
  value       = var.aws_region
}


output "s3_bucket_name" {
  description = "S3 bucket containing the payments landing zone."
  value       = aws_s3_bucket.payments_landing.id
}


output "s3_landing_url" {
  description = "S3 path governed by the Databricks external location."

  value = (
    "s3://${aws_s3_bucket.payments_landing.id}/${local.landing_prefix}"
  )
}


output "unity_catalog_iam_role_name" {
  description = "IAM role used by the Unity Catalog storage credential."
  value       = aws_iam_role.unity_catalog_s3_access.name
}


output "unity_catalog_iam_role_arn" {
  description = "IAM role ARN used by the Unity Catalog storage credential."
  value       = aws_iam_role.unity_catalog_s3_access.arn
}


# ===================================================================
# Optional MSK outputs
# ===================================================================

output "msk_enabled" {
  description = "Whether the optional Amazon MSK stack is enabled."
  value       = var.enable_msk
}


output "msk_vpc_id" {
  description = "VPC created for the optional Amazon MSK streaming platform."

  value = try(
    aws_vpc.msk[0].id,
    null
  )
}


output "msk_public_subnet_ids" {
  description = "Public subnet IDs used by Amazon MSK when enabled."

  value = [
    for subnet in aws_subnet.msk_public :
    subnet.id
  ]
}


output "msk_public_subnet_availability_zones" {
  description = "Availability Zones used by the Amazon MSK public subnets."

  value = [
    for subnet in aws_subnet.msk_public :
    subnet.availability_zone
  ]
}


output "msk_security_group_id" {
  description = "Security group protecting the Amazon MSK brokers."

  value = try(
    aws_security_group.msk[0].id,
    null
  )
}


output "msk_cluster_name" {
  description = "Name of the Enterprise Payments Amazon MSK cluster when enabled."

  value = try(
    aws_msk_cluster.payments_streaming[0].cluster_name,
    null
  )
}


output "msk_cluster_arn" {
  description = "ARN of the Enterprise Payments Amazon MSK cluster when enabled."

  value = try(
    aws_msk_cluster.payments_streaming[0].arn,
    null
  )
}


output "msk_cluster_current_version" {
  description = "Current Amazon MSK cluster version when enabled."

  value = try(
    aws_msk_cluster.payments_streaming[0].current_version,
    null
  )
}


output "msk_private_bootstrap_brokers_sasl_iam" {
  description = "Private SASL/IAM Kafka bootstrap broker endpoints when MSK is enabled."

  value = try(
    aws_msk_cluster.payments_streaming[0].bootstrap_brokers_sasl_iam,
    null
  )
}


output "msk_public_bootstrap_brokers_sasl_iam" {
  description = <<-EOT
    Public SASL/IAM Kafka bootstrap broker endpoints.

    null when MSK is disabled.

    The value can also be empty while the cluster exists but public
    broker connectivity has not yet been enabled.
  EOT

  value = try(
    aws_msk_cluster.payments_streaming[0].bootstrap_brokers_public_sasl_iam,
    null
  )
}


output "msk_databricks_iam_role_name" {
  description = "IAM role used by the Databricks MSK service credential when enabled."

  value = try(
    aws_iam_role.msk_databricks[0].name,
    null
  )
}


output "msk_databricks_iam_role_arn" {
  description = "IAM role ARN used by the Databricks MSK service credential when enabled."

  value = try(
    aws_iam_role.msk_databricks[0].arn,
    null
  )
}