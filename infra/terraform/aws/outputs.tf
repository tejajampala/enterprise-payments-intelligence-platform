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