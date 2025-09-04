output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for EKS cluster"
  value       = aws_cloudwatch_log_group.eks.name
}

output "cloudwatch_log_group_arn" {
  description = "ARN of the CloudWatch log group for EKS cluster"
  value       = aws_cloudwatch_log_group.eks.arn
}

output "application_log_group_name" {
  description = "Name of the CloudWatch log group for applications"
  value       = aws_cloudwatch_log_group.applications.name
}

output "application_log_group_arn" {
  description = "ARN of the CloudWatch log group for applications"
  value       = aws_cloudwatch_log_group.applications.arn
}

output "query_engine_log_group_name" {
  description = "Name of the CloudWatch log group for query engines"
  value       = aws_cloudwatch_log_group.query_engines.name
}

output "query_engine_log_group_arn" {
  description = "ARN of the CloudWatch log group for query engines"
  value       = aws_cloudwatch_log_group.query_engines.arn
}

output "cloudwatch_dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.cluster.dashboard_name
}

output "cloudwatch_dashboard_arn" {
  description = "ARN of the CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.cluster.dashboard_arn
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for alarms"
  value       = aws_sns_topic.alarms.arn
}

output "sns_topic_name" {
  description = "Name of the SNS topic for alarms"
  value       = aws_sns_topic.alarms.name
}
