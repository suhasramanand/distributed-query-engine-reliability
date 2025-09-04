variable "environment" {
  description = "Environment name"
  type        = string
}

variable "cluster_name" {
  description = "Name of the cluster"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where EFS will be created"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for EFS mount targets"
  type        = list(string)
}

variable "cluster_security_group_ids" {
  description = "List of security group IDs for cluster access to EFS"
  type        = list(string)
  default     = []
}

variable "query_engine_role_arns" {
  description = "List of IAM role ARNs for query engines to access S3"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}
