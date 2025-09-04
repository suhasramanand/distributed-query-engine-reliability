# Production Environment Configuration
environment = "prod"
aws_region  = "us-west-2"

# Cluster Configuration
cluster_name    = "distributed-query-engine-prod"
cluster_version = "1.28"

# Networking
vpc_cidr = "10.0.0.0/16"
availability_zones = [
  "us-west-2a",
  "us-west-2b",
  "us-west-2c"
]

# Node Groups Configuration
node_groups = {
  general = {
    desired_capacity = 3
    max_capacity     = 10
    min_capacity     = 1
    instance_types   = ["m5.large", "m5.xlarge"]
    capacity_type    = "ON_DEMAND"
    labels = {
      Environment = "prod"
      NodeGroup   = "general"
    }
    taints = []
  }
  
  analytics = {
    desired_capacity = 2
    max_capacity     = 8
    min_capacity     = 1
    instance_types   = ["r5.xlarge", "r5.2xlarge"]
    capacity_type    = "ON_DEMAND"
    labels = {
      Environment = "prod"
      NodeGroup   = "analytics"
    }
    taints = [{
      key    = "dedicated"
      value  = "analytics"
      effect = "NO_SCHEDULE"
    }]
  }
}

# Features
enable_autoscaling = true
enable_monitoring  = true
enable_logging     = true

# Tags
tags = {
  Environment = "production"
  Project     = "distributed-query-engine"
  Owner       = "data-team"
  CostCenter  = "analytics"
}
