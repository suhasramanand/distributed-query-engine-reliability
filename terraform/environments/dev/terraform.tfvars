# Development Environment Configuration
environment = "dev"
aws_region  = "us-west-2"

# Cluster Configuration
cluster_name    = "distributed-query-engine-dev"
cluster_version = "1.28"

# Networking
vpc_cidr = "10.1.0.0/16"
availability_zones = [
  "us-west-2a",
  "us-west-2b"
]

# Node Groups Configuration
node_groups = {
  general = {
    desired_capacity = 2
    max_capacity     = 5
    min_capacity     = 1
    instance_types   = ["m5.large"]
    capacity_type    = "ON_DEMAND"
    labels = {
      Environment = "dev"
      NodeGroup   = "general"
    }
    taints = []
  }
  
  analytics = {
    desired_capacity = 1
    max_capacity     = 3
    min_capacity     = 1
    instance_types   = ["r5.xlarge"]
    capacity_type    = "ON_DEMAND"
    labels = {
      Environment = "dev"
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
  Environment = "development"
  Project     = "distributed-query-engine"
  Owner       = "data-team"
  CostCenter  = "analytics"
}
