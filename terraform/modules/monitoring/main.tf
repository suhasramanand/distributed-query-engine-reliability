terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# CloudWatch Log Group for EKS cluster logs
resource "aws_cloudwatch_log_group" "eks" {
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = 30

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-eks-logs"
  })
}

# CloudWatch Log Group for application logs
resource "aws_cloudwatch_log_group" "applications" {
  name              = "/aws/eks/${var.cluster_name}/applications"
  retention_in_days = 30

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-application-logs"
  })
}

# CloudWatch Log Group for query engine logs
resource "aws_cloudwatch_log_group" "query_engines" {
  name              = "/aws/eks/${var.cluster_name}/query-engines"
  retention_in_days = 30

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-query-engine-logs"
  })
}

# CloudWatch Dashboard for cluster monitoring
resource "aws_cloudwatch_dashboard" "cluster" {
  dashboard_name = "${var.cluster_name}-cluster-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/EKS", "cluster_failed_node_count", "ClusterName", var.cluster_name],
            [".", "cluster_node_count", ".", "."],
            [".", "cluster_control_plane_request_duration", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "EKS Cluster Metrics"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/EC2", "CPUUtilization", "AutoScalingGroupName", "${var.cluster_name}-node-group"],
            [".", "NetworkIn", ".", "."],
            [".", "NetworkOut", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "Node Group Metrics"
        }
      }
    ]
  })
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "cluster_health" {
  alarm_name          = "${var.cluster_name}-cluster-health"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "cluster_failed_node_count"
  namespace           = "AWS/EKS"
  period              = "300"
  statistic           = "Average"
  threshold           = "0"
  alarm_description   = "This metric monitors EKS cluster failed node count"
  alarm_actions       = var.alarm_actions

  dimensions = {
    ClusterName = var.cluster_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "node_cpu" {
  alarm_name          = "${var.cluster_name}-node-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors EC2 instance CPU utilization"
  alarm_actions       = var.alarm_actions

  dimensions = {
    AutoScalingGroupName = "${var.cluster_name}-node-group"
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "node_memory" {
  alarm_name          = "${var.cluster_name}-node-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "85"
  alarm_description   = "This metric monitors EC2 instance memory utilization"
  alarm_actions       = var.alarm_actions

  dimensions = {
    AutoScalingGroupName = "${var.cluster_name}-node-group"
  }

  tags = var.tags
}

# SNS Topic for alarms
resource "aws_sns_topic" "alarms" {
  name = "${var.cluster_name}-alarms"

  tags = var.tags
}

# SNS Topic Policy
resource "aws_sns_topic_policy" "alarms" {
  arn = aws_sns_topic.alarms.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "cloudwatch.amazonaws.com"
        }
        Action = [
          "SNS:Publish"
        ]
        Resource = aws_sns_topic.alarms.arn
      }
    ]
  })
}

# Data sources
data "aws_region" "current" {}
