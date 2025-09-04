output "s3_bucket_name" {
  description = "Name of the S3 bucket for data storage"
  value       = aws_s3_bucket.data.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for data storage"
  value       = aws_s3_bucket.data.arn
}

output "s3_bucket_id" {
  description = "ID of the S3 bucket for data storage"
  value       = aws_s3_bucket.data.id
}

output "efs_file_system_id" {
  description = "ID of the EFS file system"
  value       = aws_efs_file_system.persistent.id
}

output "efs_file_system_arn" {
  description = "ARN of the EFS file system"
  value       = aws_efs_file_system.persistent.arn
}

output "efs_access_point_id" {
  description = "ID of the EFS access point for query engines"
  value       = aws_efs_access_point.query_engines.id
}

output "efs_access_point_arn" {
  description = "ARN of the EFS access point for query engines"
  value       = aws_efs_access_point.query_engines.arn
}

output "efs_mount_target_ids" {
  description = "List of EFS mount target IDs"
  value       = aws_efs_mount_target.persistent[*].id
}

output "efs_security_group_id" {
  description = "Security group ID for EFS"
  value       = aws_security_group.efs.id
}
