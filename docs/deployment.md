# Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Distributed Query Engine Reliability project on Kubernetes.

## Prerequisites

### Required Tools

- **Terraform** >= 1.0
- **kubectl** >= 1.24
- **helm** >= 3.8
- **Docker** >= 20.0
- **AWS CLI** >= 2.0
- **Python** >= 3.9

### AWS Requirements

- AWS Account with appropriate permissions
- AWS CLI configured with access keys
- S3 bucket for Terraform state (optional but recommended)
- ECR repository for custom images (optional)

### System Requirements

- **CPU**: 8+ cores recommended
- **Memory**: 16GB+ RAM
- **Storage**: 100GB+ free space
- **Network**: Stable internet connection

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/suhasramanand/distributed-query-engine-reliability.git
cd distributed-query-engine-reliability
```

### 2. Configure AWS Credentials

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-west-2"
```

### 3. Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan -var-file=environments/prod/terraform.tfvars
terraform apply -var-file=environments/prod/terraform.tfvars
```

### 4. Deploy Applications

```bash
cd ../helm
./deploy-all.sh
```

### 5. Verify Deployment

```bash
kubectl get pods --all-namespaces
kubectl get services --all-namespaces
```

## Detailed Deployment Steps

### Step 1: Infrastructure Setup

#### 1.1 Configure Terraform Backend (Optional)

Create an S3 bucket for Terraform state:

```bash
aws s3 mb s3://distributed-query-engine-terraform-state
```

Update the backend configuration in `terraform/main.tf`:

```hcl
backend "s3" {
  bucket = "distributed-query-engine-terraform-state"
  key    = "prod/terraform.tfstate"
  region = "us-west-2"
}
```

#### 1.2 Initialize Terraform

```bash
cd terraform
terraform init
```

#### 1.3 Review Configuration

Review the configuration in `environments/prod/terraform.tfvars`:

```hcl
environment = "prod"
aws_region  = "us-west-2"
cluster_name = "distributed-query-engine-prod"
cluster_version = "1.28"
vpc_cidr = "10.0.0.0/16"
availability_zones = ["us-west-2a", "us-west-2b", "us-west-2c"]
```

#### 1.4 Deploy Infrastructure

```bash
terraform plan -var-file=environments/prod/terraform.tfvars
terraform apply -var-file=environments/prod/terraform.tfvars
```

This will create:
- VPC with public/private subnets
- EKS cluster with node groups
- S3 buckets for data storage
- CloudWatch log groups
- IAM roles and policies

#### 1.5 Configure kubectl

```bash
aws eks update-kubeconfig --name distributed-query-engine-prod --region us-west-2
```

### Step 2: Application Deployment

#### 2.1 Deploy Monitoring Stack

```bash
cd helm/monitoring
helm upgrade --install monitoring . \
  --namespace monitoring \
  --create-namespace \
  --wait \
  --timeout 10m \
  --set prometheus.enabled=true \
  --set grafana.enabled=true \
  --set alertmanager.enabled=true
```

#### 2.2 Deploy Spark Operator

```bash
cd ../spark-operator
helm upgrade --install spark-operator . \
  --namespace query-engines \
  --create-namespace \
  --wait \
  --timeout 10m
```

#### 2.3 Deploy ClickHouse

```bash
cd ../clickhouse
helm upgrade --install clickhouse . \
  --namespace query-engines \
  --create-namespace \
  --wait \
  --timeout 15m \
  --set replicaCount.shard=3 \
  --set replicaCount.replica=2
```

#### 2.4 Deploy Presto

```bash
cd ../presto
helm upgrade --install presto . \
  --namespace query-engines \
  --create-namespace \
  --wait \
  --timeout 15m \
  --set replicaCount.coordinator=1 \
  --set replicaCount.worker=3
```

#### 2.5 Deploy Chaos Mesh

```bash
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update
helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh \
  --namespace chaos-mesh \
  --create-namespace \
  --wait \
  --timeout 10m
```

### Step 3: Verification

#### 3.1 Check Pod Status

```bash
kubectl get pods --all-namespaces
```

All pods should be in `Running` state.

#### 3.2 Check Services

```bash
kubectl get services --all-namespaces
```

Verify all services are created and have endpoints.

#### 3.3 Run Health Checks

```bash
# Test Presto
kubectl run test-presto --image=curlimages/curl -n query-engines --rm -i --restart=Never -- \
  curl -f http://presto-coordinator:8080/v1/info

# Test ClickHouse
kubectl run test-clickhouse --image=curlimages/curl -n query-engines --rm -i --restart=Never -- \
  curl -f http://clickhouse:8123/ping

# Test Prometheus
kubectl run test-prometheus --image=curlimages/curl -n monitoring --rm -i --restart=Never -- \
  curl -f http://prometheus:9090/-/healthy
```

### Step 4: Configuration

#### 4.1 Configure Data Sources

Create S3 buckets for data storage:

```bash
aws s3 mb s3://distributed-query-engine-prod-data
aws s3 mb s3://distributed-query-engine-prod-logs
```

#### 4.2 Configure Monitoring

Access Grafana dashboard:

```bash
kubectl port-forward svc/grafana 3000:3000 -n monitoring
```

Default credentials:
- Username: `admin`
- Password: `admin123`

#### 4.3 Configure Alerts

Update Alertmanager configuration for your notification channels:

```yaml
receivers:
  - name: 'slack'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
        channel: '#alerts'
```

### Step 5: Testing

#### 5.1 Run Benchmarks

```bash
cd benchmarks
python tpch/run_presto_benchmarks.py \
  --presto-host presto-coordinator \
  --presto-port 8080 \
  --catalog hive \
  --schema tpch \
  --scale-factor 10 \
  --output-file presto_tpch_results.json
```

#### 5.2 Run Fault Injection Tests

```bash
cd fault-tests
python recovery-tests/recovery_test.py \
  --namespace query-engines \
  --output-file recovery_results.json \
  --test-type comprehensive
```

## Environment-Specific Configurations

### Development Environment

For development, use smaller resource allocations:

```bash
cd terraform
terraform apply -var-file=environments/dev/terraform.tfvars
```

### Production Environment

For production, ensure high availability:

```bash
# Use production configuration
terraform apply -var-file=environments/prod/terraform.tfvars

# Deploy with production settings
cd helm
./deploy-all.sh
```

## Troubleshooting

### Common Issues

#### 1. Pod Startup Issues

Check pod logs:

```bash
kubectl logs <pod-name> -n <namespace>
```

#### 2. Resource Constraints

Check resource usage:

```bash
kubectl top pods --all-namespaces
kubectl describe node
```

#### 3. Network Issues

Check network connectivity:

```bash
kubectl run test-connectivity --image=curlimages/curl -n query-engines --rm -i --restart=Never -- \
  curl -v http://presto-coordinator:8080/v1/info
```

#### 4. Storage Issues

Check persistent volumes:

```bash
kubectl get pv
kubectl get pvc --all-namespaces
```

### Debugging Commands

#### Check Cluster Status

```bash
kubectl cluster-info
kubectl get nodes
kubectl get pods --all-namespaces
```

#### Check Service Endpoints

```bash
kubectl get endpoints --all-namespaces
kubectl describe service <service-name> -n <namespace>
```

#### Check Events

```bash
kubectl get events --all-namespaces --sort-by='.lastTimestamp'
```

## Monitoring and Maintenance

### Regular Maintenance Tasks

#### 1. Update Components

```bash
# Update Helm charts
helm repo update
helm upgrade <release-name> <chart-name> -n <namespace>

# Update Kubernetes cluster
eksctl upgrade cluster --name distributed-query-engine-prod --region us-west-2
```

#### 2. Backup Configuration

```bash
# Backup Helm releases
helm list --all-namespaces -o yaml > helm-releases-backup.yaml

# Backup Kubernetes resources
kubectl get all --all-namespaces -o yaml > k8s-resources-backup.yaml
```

#### 3. Monitor Performance

```bash
# Check resource usage
kubectl top pods --all-namespaces
kubectl top nodes

# Check query performance
kubectl logs -f deployment/presto-coordinator -n query-engines
```

### Scaling Operations

#### Scale Query Engines

```bash
# Scale Presto workers
kubectl scale deployment presto-worker --replicas=5 -n query-engines

# Scale ClickHouse
kubectl scale statefulset clickhouse --replicas=6 -n query-engines
```

#### Scale Infrastructure

```bash
# Scale node groups
aws eks update-nodegroup-config \
  --cluster-name distributed-query-engine-prod \
  --nodegroup-name analytics \
  --scaling-config minSize=2,maxSize=10,desiredSize=4
```

## Security Considerations

### Access Control

#### 1. RBAC Configuration

```bash
# Create service accounts
kubectl create serviceaccount query-engine-sa -n query-engines

# Create roles and bindings
kubectl create role query-engine-role --verb=get,list,watch --resource=pods,services -n query-engines
kubectl create rolebinding query-engine-binding --role=query-engine-role --serviceaccount=query-engines:query-engine-sa -n query-engines
```

#### 2. Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: query-engine-network-policy
  namespace: query-engines
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: presto
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
    ports:
    - protocol: TCP
      port: 8080
```

### Data Security

#### 1. Encrypt Data at Rest

```bash
# Enable encryption for EBS volumes
aws ec2 enable-ebs-encryption-by-default

# Enable encryption for S3 buckets
aws s3api put-bucket-encryption \
  --bucket distributed-query-engine-prod-data \
  --server-side-encryption-configuration '{
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        }
      }
    ]
  }'
```

#### 2. Secure Communication

```bash
# Enable TLS for query engines
kubectl create secret tls query-engine-tls \
  --cert=tls.crt \
  --key=tls.key \
  -n query-engines
```

## Cost Optimization

### Resource Optimization

#### 1. Use Spot Instances

```bash
# Configure spot instances for non-critical workloads
aws eks create-nodegroup \
  --cluster-name distributed-query-engine-prod \
  --nodegroup-name spot-workers \
  --capacity-type SPOT \
  --instance-types m5.large,m5.xlarge
```

#### 2. Implement Auto-scaling

```bash
# Enable cluster autoscaler
kubectl apply -f https://raw.githubusercontent.com/kubernetes/autoscaler/master/cluster-autoscaler/cloudprovider/aws/examples/cluster-autoscaler-autodiscover.yaml
```

#### 3. Monitor Costs

```bash
# Set up cost monitoring
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

## Support and Resources

### Documentation

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)
- [Terraform Documentation](https://www.terraform.io/docs/)
- [AWS EKS Documentation](https://docs.aws.amazon.com/eks/)

### Community Resources

- [Kubernetes Slack](https://slack.k8s.io/)
- [Helm Slack](https://slack.helm.sh/)
- [Terraform Community](https://www.terraform.io/community)

### Getting Help

For issues specific to this project:

1. Check the troubleshooting section above
2. Review logs and error messages
3. Search existing issues in the repository
4. Create a new issue with detailed information

## Conclusion

This deployment guide provides comprehensive instructions for setting up the Distributed Query Engine Reliability project. Follow the steps carefully and ensure all prerequisites are met before proceeding with deployment.

For production deployments, consider additional security measures, monitoring, and backup strategies based on your specific requirements.
