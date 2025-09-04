# Troubleshooting Guide

## Overview

This guide provides solutions for common issues encountered when deploying and operating the Distributed Query Engine Reliability project.

## Quick Diagnostic Commands

### Cluster Health Check

```bash
# Check cluster status
kubectl cluster-info
kubectl get nodes
kubectl get pods --all-namespaces

# Check events
kubectl get events --all-namespaces --sort-by='.lastTimestamp'

# Check resource usage
kubectl top nodes
kubectl top pods --all-namespaces
```

### Service Health Check

```bash
# Check services and endpoints
kubectl get services --all-namespaces
kubectl get endpoints --all-namespaces

# Test connectivity
kubectl run test-connectivity --image=curlimages/curl -n query-engines --rm -i --restart=Never -- \
  curl -v http://presto-coordinator:8080/v1/info
```

## Common Issues and Solutions

### 1. Infrastructure Issues

#### 1.1 Terraform Deployment Failures

**Problem**: Terraform apply fails with AWS API errors

**Symptoms**:
- `Error: error creating EKS cluster`
- `Error: error creating VPC`
- `Error: InsufficientInstanceCapacity`

**Solutions**:

1. **Check AWS Credentials**:
```bash
aws sts get-caller-identity
aws eks list-clusters
```

2. **Verify Resource Limits**:
```bash
# Check EKS service quotas
aws service-quotas get-service-quota \
  --service-code eks \
  --quota-code L-1194D53C

# Check VPC limits
aws ec2 describe-account-attributes
```

3. **Use Different Region/AZ**:
```bash
# Update terraform.tfvars
aws_region = "us-east-1"
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
```

4. **Clean Up and Retry**:
```bash
terraform destroy -var-file=environments/prod/terraform.tfvars
terraform apply -var-file=environments/prod/terraform.tfvars
```

#### 1.2 EKS Cluster Issues

**Problem**: EKS cluster not accessible or nodes not joining

**Symptoms**:
- `kubectl cluster-info` fails
- Nodes not showing up in cluster
- Pods stuck in Pending state

**Solutions**:

1. **Check Cluster Status**:
```bash
aws eks describe-cluster --name distributed-query-engine-prod --region us-west-2
```

2. **Verify Node Groups**:
```bash
aws eks list-nodegroups --cluster-name distributed-query-engine-prod --region us-west-2
aws eks describe-nodegroup --cluster-name distributed-query-engine-prod --nodegroup-name general --region us-west-2
```

3. **Check IAM Roles**:
```bash
# Verify node IAM role
aws iam get-role --role-name AmazonEKSNodeRole
aws iam list-attached-role-policies --role-name AmazonEKSNodeRole
```

4. **Update kubeconfig**:
```bash
aws eks update-kubeconfig --name distributed-query-engine-prod --region us-west-2
```

### 2. Application Deployment Issues

#### 2.1 Helm Chart Deployment Failures

**Problem**: Helm deployment fails or times out

**Symptoms**:
- `Error: timed out waiting for the condition`
- `Error: release failed`
- Pods not starting

**Solutions**:

1. **Check Helm Status**:
```bash
helm list --all-namespaces
helm status <release-name> -n <namespace>
```

2. **Verify Chart Dependencies**:
```bash
helm dependency update helm/presto
helm dependency build helm/presto
```

3. **Check Resource Requirements**:
```bash
# Verify node resources
kubectl describe node
kubectl top nodes

# Check resource requests/limits
kubectl get pods -n query-engines -o yaml | grep -A 5 resources:
```

4. **Debug Pod Issues**:
```bash
# Check pod events
kubectl describe pod <pod-name> -n <namespace>

# Check pod logs
kubectl logs <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous
```

#### 2.2 Presto/Trino Issues

**Problem**: Presto coordinator or workers not starting

**Symptoms**:
- Coordinator pod in CrashLoopBackOff
- Workers not connecting to coordinator
- Query failures

**Solutions**:

1. **Check Coordinator Logs**:
```bash
kubectl logs -f deployment/presto-coordinator -n query-engines
```

2. **Verify Configuration**:
```bash
# Check config maps
kubectl get configmaps -n query-engines
kubectl describe configmap presto-config -n query-engines

# Check secrets
kubectl get secrets -n query-engines
```

3. **Test Coordinator Health**:
```bash
kubectl run test-presto --image=curlimages/curl -n query-engines --rm -i --restart=Never -- \
  curl -f http://presto-coordinator:8080/v1/info
```

4. **Check Worker Connectivity**:
```bash
# Check worker logs
kubectl logs -f deployment/presto-worker -n query-engines

# Test worker to coordinator connectivity
kubectl exec -it deployment/presto-worker -n query-engines -- \
  curl -f http://presto-coordinator:8080/v1/info
```

#### 2.3 ClickHouse Issues

**Problem**: ClickHouse cluster not forming or queries failing

**Symptoms**:
- Shards not replicating
- Queries timing out
- Memory errors

**Solutions**:

1. **Check Cluster Status**:
```bash
kubectl exec -it statefulset/clickhouse -n query-engines -- \
  clickhouse-client --query "SELECT * FROM system.clusters"
```

2. **Verify Replication**:
```bash
kubectl exec -it statefulset/clickhouse -n query-engines -- \
  clickhouse-client --query "SELECT * FROM system.replicas"
```

3. **Check Resource Usage**:
```bash
kubectl exec -it statefulset/clickhouse -n query-engines -- \
  clickhouse-client --query "SELECT * FROM system.metrics WHERE metric LIKE '%memory%'"
```

4. **Test Connectivity**:
```bash
kubectl run test-clickhouse --image=curlimages/curl -n query-engines --rm -i --restart=Never -- \
  curl -f http://clickhouse:8123/ping
```

#### 2.4 Spark Operator Issues

**Problem**: Spark applications not starting or failing

**Symptoms**:
- SparkApplication in Failed state
- Driver pods not starting
- Executor pods not joining

**Solutions**:

1. **Check Operator Status**:
```bash
kubectl get pods -n query-engines -l app.kubernetes.io/name=spark-operator
kubectl logs -f deployment/spark-operator -n query-engines
```

2. **Verify SparkApplication**:
```bash
kubectl get sparkapplications -n query-engines
kubectl describe sparkapplication <app-name> -n query-engines
```

3. **Check Driver Logs**:
```bash
kubectl logs -f sparkapplication-<app-name>-driver -n query-engines
```

4. **Verify Resource Allocation**:
```bash
kubectl get pods -n query-engines -l spark-role=driver
kubectl describe pod sparkapplication-<app-name>-driver -n query-engines
```

### 3. Monitoring Issues

#### 3.1 Prometheus Issues

**Problem**: Prometheus not collecting metrics or targets down

**Symptoms**:
- Targets showing as down in Prometheus UI
- No metrics being collected
- Prometheus pod not starting

**Solutions**:

1. **Check Prometheus Status**:
```bash
kubectl get pods -n monitoring -l app=prometheus
kubectl logs -f deployment/prometheus -n monitoring
```

2. **Verify Service Monitors**:
```bash
kubectl get servicemonitors -n monitoring
kubectl describe servicemonitor presto-monitor -n monitoring
```

3. **Test Target Endpoints**:
```bash
# Test Presto metrics endpoint
kubectl run test-presto-metrics --image=curlimages/curl -n query-engines --rm -i --restart=Never -- \
  curl -f http://presto-coordinator:8080/metrics

# Test ClickHouse metrics endpoint
kubectl run test-clickhouse-metrics --image=curlimages/curl -n query-engines --rm -i --restart=Never -- \
  curl -f http://clickhouse:8123/metrics
```

4. **Check Prometheus Configuration**:
```bash
kubectl get configmap prometheus-config -n monitoring -o yaml
```

#### 3.2 Grafana Issues

**Problem**: Grafana not accessible or dashboards not loading

**Symptoms**:
- Grafana login fails
- Dashboards showing no data
- Grafana pod not starting

**Solutions**:

1. **Check Grafana Status**:
```bash
kubectl get pods -n monitoring -l app=grafana
kubectl logs -f deployment/grafana -n monitoring
```

2. **Verify Data Sources**:
```bash
# Access Grafana and check data sources
kubectl port-forward svc/grafana 3000:3000 -n monitoring
# Navigate to http://localhost:3000 and check Data Sources
```

3. **Check Persistent Volume**:
```bash
kubectl get pvc -n monitoring
kubectl describe pvc grafana-pvc -n monitoring
```

4. **Reset Grafana Admin Password**:
```bash
kubectl exec -it deployment/grafana -n monitoring -- \
  grafana-cli admin reset-admin-password admin123
```

### 4. Performance Issues

#### 4.1 Query Performance Degradation

**Problem**: Queries running slower than expected

**Symptoms**:
- Query execution time increasing
- High CPU/memory usage
- Timeout errors

**Solutions**:

1. **Check Resource Usage**:
```bash
kubectl top pods --all-namespaces
kubectl describe node
```

2. **Analyze Query Plans**:
```bash
# For Presto
kubectl exec -it deployment/presto-coordinator -n query-engines -- \
  presto-cli --server presto-coordinator:8080 --execute "EXPLAIN (TYPE DISTRIBUTED) SELECT * FROM tpch.lineitem LIMIT 1000"

# For ClickHouse
kubectl exec -it statefulset/clickhouse -n query-engines -- \
  clickhouse-client --query "EXPLAIN SELECT * FROM system.numbers LIMIT 1000"
```

3. **Check Cluster Scaling**:
```bash
# Check HPA status
kubectl get hpa -n query-engines
kubectl describe hpa presto-worker-hpa -n query-engines

# Check node group scaling
aws eks describe-nodegroup --cluster-name distributed-query-engine-prod --nodegroup-name analytics --region us-west-2
```

4. **Optimize Configuration**:
```bash
# Check current Presto config
kubectl get configmap presto-config -n query-engines -o yaml

# Check current ClickHouse config
kubectl get configmap clickhouse-config -n query-engines -o yaml
```

#### 4.2 Memory Issues

**Problem**: Out of memory errors or high memory usage

**Symptoms**:
- OOMKilled pods
- High memory usage
- Query failures due to memory

**Solutions**:

1. **Check Memory Usage**:
```bash
kubectl top pods --all-namespaces --sort-by=cpu
kubectl describe node | grep -A 10 "Allocated resources"
```

2. **Adjust Memory Limits**:
```bash
# Update Presto memory settings
helm upgrade presto helm/presto -n query-engines \
  --set coordinator.resources.limits.memory=8Gi \
  --set worker.resources.limits.memory=16Gi

# Update ClickHouse memory settings
helm upgrade clickhouse helm/clickhouse -n query-engines \
  --set server.resources.limits.memory=32Gi
```

3. **Enable Memory Monitoring**:
```bash
# Check memory metrics in Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n monitoring
# Navigate to http://localhost:9090 and query memory metrics
```

### 5. Network Issues

#### 5.1 Service Discovery Issues

**Problem**: Services not reachable or DNS resolution failing

**Symptoms**:
- Connection refused errors
- DNS resolution failures
- Service endpoints empty

**Solutions**:

1. **Check Service Endpoints**:
```bash
kubectl get endpoints --all-namespaces
kubectl describe service presto-coordinator -n query-engines
```

2. **Test DNS Resolution**:
```bash
kubectl run test-dns --image=busybox -n query-engines --rm -i --restart=Never -- \
  nslookup presto-coordinator
```

3. **Check Network Policies**:
```bash
kubectl get networkpolicies --all-namespaces
kubectl describe networkpolicy -n query-engines
```

4. **Verify CoreDNS**:
```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -f deployment/coredns -n kube-system
```

#### 5.2 Load Balancer Issues

**Problem**: External access not working or load balancer not created

**Symptoms**:
- External IP not assigned
- Load balancer health checks failing
- Connection timeouts

**Solutions**:

1. **Check Load Balancer Status**:
```bash
kubectl get services --all-namespaces
aws elbv2 describe-load-balancers --region us-west-2
```

2. **Verify Security Groups**:
```bash
aws ec2 describe-security-groups --filters "Name=group-name,Values=*eks*" --region us-west-2
```

3. **Check Target Group Health**:
```bash
aws elbv2 describe-target-groups --region us-west-2
aws elbv2 describe-target-health --target-group-arn <target-group-arn> --region us-west-2
```

### 6. Storage Issues

#### 6.1 Persistent Volume Issues

**Problem**: PVC not bound or storage not accessible

**Symptoms**:
- PVC in Pending state
- Pod startup failures
- Data loss

**Solutions**:

1. **Check PVC Status**:
```bash
kubectl get pvc --all-namespaces
kubectl describe pvc <pvc-name> -n <namespace>
```

2. **Verify Storage Class**:
```bash
kubectl get storageclass
kubectl describe storageclass gp2
```

3. **Check EBS Volumes**:
```bash
aws ec2 describe-volumes --filters "Name=tag:kubernetes.io/cluster/distributed-query-engine-prod,Values=owned" --region us-west-2
```

4. **Recover from Storage Issues**:
```bash
# Delete and recreate PVC (data will be lost)
kubectl delete pvc <pvc-name> -n <namespace>
kubectl apply -f pvc.yaml
```

#### 6.2 S3 Access Issues

**Problem**: Query engines cannot access S3 data

**Symptoms**:
- S3 access denied errors
- Query failures on S3 tables
- Authentication errors

**Solutions**:

1. **Verify IAM Roles**:
```bash
# Check node IAM role
aws iam get-role --role-name AmazonEKSNodeRole
aws iam list-attached-role-policies --role-name AmazonEKSNodeRole

# Check S3 bucket policy
aws s3api get-bucket-policy --bucket distributed-query-engine-prod-data
```

2. **Test S3 Access**:
```bash
kubectl run test-s3 --image=amazon/aws-cli -n query-engines --rm -i --restart=Never -- \
  aws s3 ls s3://distributed-query-engine-prod-data
```

3. **Update S3 Permissions**:
```bash
# Add S3 read permissions to node role
aws iam attach-role-policy \
  --role-name AmazonEKSNodeRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
```

### 7. Security Issues

#### 7.1 RBAC Issues

**Problem**: Permission denied errors or service accounts not working

**Symptoms**:
- Permission denied errors
- Service account not found
- Role binding issues

**Solutions**:

1. **Check RBAC Configuration**:
```bash
kubectl get serviceaccounts --all-namespaces
kubectl get roles --all-namespaces
kubectl get rolebindings --all-namespaces
```

2. **Verify Service Account**:
```bash
kubectl describe serviceaccount presto-sa -n query-engines
kubectl get secrets -n query-engines
```

3. **Check Pod Service Account**:
```bash
kubectl describe pod <pod-name> -n query-engines | grep ServiceAccount
```

#### 7.2 Network Policy Issues

**Problem**: Network policies blocking legitimate traffic

**Symptoms**:
- Connection refused between pods
- Service discovery failing
- Monitoring not working

**Solutions**:

1. **Check Network Policies**:
```bash
kubectl get networkpolicies --all-namespaces
kubectl describe networkpolicy -n query-engines
```

2. **Test Connectivity**:
```bash
# Test pod-to-pod connectivity
kubectl run test-connectivity --image=curlimages/curl -n query-engines --rm -i --restart=Never -- \
  curl -f http://presto-coordinator:8080/v1/info
```

3. **Temporarily Disable Network Policies**:
```bash
kubectl delete networkpolicy --all -n query-engines
```

### 8. Chaos Engineering Issues

#### 8.1 Chaos Mesh Issues

**Problem**: Chaos experiments not working or causing unexpected failures

**Symptoms**:
- Chaos experiments not starting
- Experiments not affecting target pods
- Cluster instability

**Solutions**:

1. **Check Chaos Mesh Status**:
```bash
kubectl get pods -n chaos-mesh
kubectl logs -f deployment/chaos-controller-manager -n chaos-mesh
```

2. **Verify Experiment Configuration**:
```bash
kubectl get chaos -n query-engines
kubectl describe podchaos <experiment-name> -n query-engines
```

3. **Test Experiment Targeting**:
```bash
# Verify pod labels match experiment selector
kubectl get pods -n query-engines --show-labels
kubectl describe podchaos <experiment-name> -n query-engines | grep -A 5 selector
```

4. **Clean Up Experiments**:
```bash
kubectl delete chaos --all -n query-engines
```

## Debugging Tools and Commands

### 1. Log Analysis

```bash
# Follow logs for all pods in namespace
kubectl logs -f --all-containers=true --tail=100 -l app=presto -n query-engines

# Search logs for errors
kubectl logs --all-containers=true -l app=presto -n query-engines | grep -i error

# Export logs for analysis
kubectl logs --all-containers=true -l app=presto -n query-engines > presto-logs.txt
```

### 2. Resource Monitoring

```bash
# Monitor resource usage in real-time
watch kubectl top pods --all-namespaces

# Check resource requests vs usage
kubectl describe node | grep -A 15 "Allocated resources"

# Monitor specific metrics
kubectl port-forward svc/prometheus 9090:9090 -n monitoring
# Navigate to http://localhost:9090 for Prometheus queries
```

### 3. Network Diagnostics

```bash
# Test network connectivity
kubectl run netcat --image=busybox -n query-engines --rm -i --restart=Never -- \
  nc -zv presto-coordinator 8080

# Check DNS resolution
kubectl run dns-test --image=busybox -n query-engines --rm -i --restart=Never -- \
  nslookup presto-coordinator

# Test service endpoints
kubectl run endpoint-test --image=curlimages/curl -n query-engines --rm -i --restart=Never -- \
  curl -v http://presto-coordinator:8080/v1/info
```

### 4. Configuration Validation

```bash
# Validate Helm charts
helm lint helm/presto
helm lint helm/clickhouse
helm lint helm/monitoring

# Validate Kubernetes manifests
kubectl apply --dry-run=client -f helm/presto/templates/
kubectl apply --dry-run=client -f helm/clickhouse/templates/

# Check Terraform configuration
terraform validate
terraform plan -var-file=environments/prod/terraform.tfvars
```

## Recovery Procedures

### 1. Complete Cluster Recovery

```bash
# Destroy and recreate infrastructure
cd terraform
terraform destroy -var-file=environments/prod/terraform.tfvars
terraform apply -var-file=environments/prod/terraform.tfvars

# Redeploy applications
cd ../helm
./deploy-all.sh
```

### 2. Application Recovery

```bash
# Restart all applications
kubectl delete pods --all -n query-engines
kubectl delete pods --all -n monitoring

# Or restart specific deployments
kubectl rollout restart deployment/presto-coordinator -n query-engines
kubectl rollout restart deployment/presto-worker -n query-engines
kubectl rollout restart statefulset/clickhouse -n query-engines
```

### 3. Data Recovery

```bash
# Restore from S3 backup (if available)
aws s3 sync s3://distributed-query-engine-prod-backup/ ./backup/

# Restore ClickHouse data
kubectl exec -it statefulset/clickhouse -n query-engines -- \
  clickhouse-client --query "RESTORE TABLE database.table FROM 's3://backup-bucket/path'"
```

## Prevention Strategies

### 1. Monitoring and Alerting

```bash
# Set up comprehensive monitoring
kubectl apply -f monitoring/prometheus-rules.yaml
kubectl apply -f monitoring/alertmanager-config.yaml

# Configure alerting channels
kubectl patch secret alertmanager-config -n monitoring --patch-file alertmanager-secret.yaml
```

### 2. Regular Maintenance

```bash
# Schedule regular backups
kubectl create cronjob backup-job --image=amazon/aws-cli -n query-engines \
  --schedule="0 2 * * *" \
  -- aws s3 sync /data s3://backup-bucket/

# Update components regularly
helm repo update
helm upgrade <release-name> <chart-name> -n <namespace>
```

### 3. Testing and Validation

```bash
# Run regular health checks
kubectl apply -f health-checks/health-check-job.yaml

# Run chaos experiments regularly
kubectl apply -f fault-tests/chaos-mesh/chaos-experiments.yaml
```

## Getting Help

### 1. Collect Diagnostic Information

```bash
# Create diagnostic bundle
kubectl cluster-info dump > cluster-info.json
kubectl get all --all-namespaces -o yaml > all-resources.yaml
kubectl get events --all-namespaces -o yaml > events.yaml
```

### 2. Check Documentation

- [Kubernetes Troubleshooting](https://kubernetes.io/docs/tasks/debug/)
- [Helm Troubleshooting](https://helm.sh/docs/chart_template_guide/debugging/)
- [AWS EKS Troubleshooting](https://docs.aws.amazon.com/eks/latest/userguide/troubleshooting.html)

### 3. Community Resources

- [Kubernetes Slack](https://slack.k8s.io/)
- [Helm Slack](https://slack.helm.sh/)
- [AWS EKS Forum](https://forums.aws.amazon.com/forum.jspa?forumID=253)

### 4. Escalation

When all troubleshooting steps fail:

1. Collect all diagnostic information
2. Document the issue timeline
3. Create a detailed bug report
4. Contact support with complete context
