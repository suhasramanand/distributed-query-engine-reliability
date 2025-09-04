#!/bin/bash

# Distributed Query Engine Deployment Script
# Deploys all components: Presto, ClickHouse, Spark Operator, and Monitoring Stack

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE_QUERY_ENGINES="query-engines"
NAMESPACE_MONITORING="monitoring"
NAMESPACE_CHAOS="chaos-mesh"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    local missing_commands=()
    
    if ! command_exists kubectl; then
        missing_commands+=("kubectl")
    fi
    
    if ! command_exists helm; then
        missing_commands+=("helm")
    fi
    
    if ! command_exists aws; then
        missing_commands+=("aws")
    fi
    
    if [ ${#missing_commands[@]} -ne 0 ]; then
        print_error "Missing required commands: ${missing_commands[*]}"
        print_error "Please install the missing commands and try again."
        exit 1
    fi
    
    print_success "All prerequisites are satisfied"
}

# Function to check cluster connectivity
check_cluster() {
    print_status "Checking cluster connectivity..."
    
    if ! kubectl cluster-info >/dev/null 2>&1; then
        print_error "Cannot connect to Kubernetes cluster"
        print_error "Please ensure kubectl is configured correctly"
        exit 1
    fi
    
    print_success "Connected to Kubernetes cluster"
}

# Function to create namespaces
create_namespaces() {
    print_status "Creating namespaces..."
    
    kubectl create namespace "$NAMESPACE_QUERY_ENGINES" --dry-run=client -o yaml | kubectl apply -f -
    kubectl create namespace "$NAMESPACE_MONITORING" --dry-run=client -o yaml | kubectl apply -f -
    kubectl create namespace "$NAMESPACE_CHAOS" --dry-run=client -o yaml | kubectl apply -f -
    
    print_success "Namespaces created"
}

# Function to deploy monitoring stack
deploy_monitoring() {
    print_status "Deploying monitoring stack..."
    
    cd monitoring
    
    helm upgrade --install monitoring . \
        --namespace "$NAMESPACE_MONITORING" \
        --create-namespace \
        --wait \
        --timeout 10m \
        --set prometheus.enabled=true \
        --set grafana.enabled=true \
        --set alertmanager.enabled=true \
        --set nodeExporter.enabled=true \
        --set kubeStateMetrics.enabled=true
    
    cd ..
    
    print_success "Monitoring stack deployed"
}

# Function to deploy Spark operator
deploy_spark_operator() {
    print_status "Deploying Spark operator..."
    
    cd spark-operator
    
    helm upgrade --install spark-operator . \
        --namespace "$NAMESPACE_QUERY_ENGINES" \
        --create-namespace \
        --wait \
        --timeout 10m \
        --set operator.webhook.enabled=true \
        --set operator.metrics.enabled=true \
        --set operator.sparkApplication.defaultSparkImage="apache/spark:3.4.1" \
        --set operator.batchScheduler.enabled=true
    
    cd ..
    
    print_success "Spark operator deployed"
}

# Function to deploy ClickHouse
deploy_clickhouse() {
    print_status "Deploying ClickHouse..."
    
    cd clickhouse
    
    helm upgrade --install clickhouse . \
        --namespace "$NAMESPACE_QUERY_ENGINES" \
        --create-namespace \
        --wait \
        --timeout 15m \
        --set replicaCount.shard=3 \
        --set replicaCount.replica=2 \
        --set resources.limits.cpu=4000m \
        --set resources.limits.memory=8Gi \
        --set resources.requests.cpu=2000m \
        --set resources.requests.memory=4Gi \
        --set autoscaling.enabled=true \
        --set autoscaling.minReplicas=3 \
        --set autoscaling.maxReplicas=12 \
        --set storage.data.size=500Gi \
        --set storage.logs.size=50Gi \
        --set monitoring.enabled=true \
        --set monitoring.prometheus.enabled=true \
        --set monitoring.grafana.enabled=true
    
    cd ..
    
    print_success "ClickHouse deployed"
}

# Function to deploy Presto
deploy_presto() {
    print_status "Deploying Presto/Trino..."
    
    cd presto
    
    helm upgrade --install presto . \
        --namespace "$NAMESPACE_QUERY_ENGINES" \
        --create-namespace \
        --wait \
        --timeout 15m \
        --set replicaCount.coordinator=1 \
        --set replicaCount.worker=3 \
        --set resources.coordinator.limits.cpu=2000m \
        --set resources.coordinator.limits.memory=4Gi \
        --set resources.coordinator.requests.cpu=1000m \
        --set resources.coordinator.requests.memory=2Gi \
        --set resources.worker.limits.cpu=4000m \
        --set resources.worker.limits.memory=8Gi \
        --set resources.worker.requests.cpu=2000m \
        --set resources.worker.requests.memory=4Gi \
        --set autoscaling.enabled=true \
        --set autoscaling.minReplicas=2 \
        --set autoscaling.maxReplicas=10 \
        --set persistence.enabled=true \
        --set persistence.size=100Gi \
        --set monitoring.enabled=true \
        --set monitoring.prometheus.enabled=true \
        --set monitoring.jmx.enabled=true \
        --set config.coordinator.query.max-memory=4GB \
        --set config.coordinator.query.max-memory-per-node=2GB \
        --set config.worker.query.max-memory=8GB \
        --set config.worker.query.max-memory-per-node=4GB
    
    cd ..
    
    print_success "Presto/Trino deployed"
}

# Function to deploy Chaos Mesh
deploy_chaos_mesh() {
    print_status "Deploying Chaos Mesh..."
    
    # Install Chaos Mesh using Helm
    helm repo add chaos-mesh https://charts.chaos-mesh.org
    helm repo update
    
    helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh \
        --namespace "$NAMESPACE_CHAOS" \
        --create-namespace \
        --wait \
        --timeout 10m \
        --set chaosDaemon.runtime=containerd \
        --set chaosDaemon.socketPath=/run/containerd/containerd.sock \
        --set controllerManager.replicaCount=1 \
        --set dashboard.enabled=true \
        --set dashboard.service.type=ClusterIP
    
    print_success "Chaos Mesh deployed"
}

# Function to verify deployments
verify_deployments() {
    print_status "Verifying deployments..."
    
    # Check if all pods are running
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        local ready_pods=$(kubectl get pods --namespace "$NAMESPACE_QUERY_ENGINES" --no-headers | grep -c "Running")
        local total_pods=$(kubectl get pods --namespace "$NAMESPACE_QUERY_ENGINES" --no-headers | wc -l)
        
        if [ "$ready_pods" -eq "$total_pods" ] && [ "$total_pods" -gt 0 ]; then
            print_success "All query engine pods are running"
            break
        fi
        
        print_status "Waiting for pods to be ready... (attempt $attempt/$max_attempts)"
        print_status "Ready: $ready_pods/$total_pods"
        
        if [ $attempt -eq $max_attempts ]; then
            print_error "Timeout waiting for pods to be ready"
            kubectl get pods --namespace "$NAMESPACE_QUERY_ENGINES"
            exit 1
        fi
        
        sleep 10
        ((attempt++))
    done
    
    # Check monitoring pods
    local monitoring_ready=$(kubectl get pods --namespace "$NAMESPACE_MONITORING" --no-headers | grep -c "Running")
    local monitoring_total=$(kubectl get pods --namespace "$NAMESPACE_MONITORING" --no-headers | wc -l)
    
    if [ "$monitoring_ready" -eq "$monitoring_total" ] && [ "$monitoring_total" -gt 0 ]; then
        print_success "All monitoring pods are running"
    else
        print_warning "Some monitoring pods are not ready: $monitoring_ready/$monitoring_total"
    fi
}

# Function to run health checks
run_health_checks() {
    print_status "Running health checks..."
    
    # Test Presto coordinator
    print_status "Testing Presto coordinator..."
    kubectl run test-presto --image=curlimages/curl -n "$NAMESPACE_QUERY_ENGINES" --rm -i --restart=Never -- \
        curl -f http://presto-coordinator:8080/v1/info || print_warning "Presto coordinator not ready"
    
    # Test ClickHouse
    print_status "Testing ClickHouse..."
    kubectl run test-clickhouse --image=curlimages/curl -n "$NAMESPACE_QUERY_ENGINES" --rm -i --restart=Never -- \
        curl -f http://clickhouse:8123/ping || print_warning "ClickHouse not ready"
    
    # Test Prometheus
    print_status "Testing Prometheus..."
    kubectl run test-prometheus --image=curlimages/curl -n "$NAMESPACE_MONITORING" --rm -i --restart=Never -- \
        curl -f http://prometheus:9090/-/healthy || print_warning "Prometheus not ready"
    
    # Test Grafana
    print_status "Testing Grafana..."
    kubectl run test-grafana --image=curlimages/curl -n "$NAMESPACE_MONITORING" --rm -i --restart=Never -- \
        curl -f http://grafana:3000/api/health || print_warning "Grafana not ready"
    
    print_success "Health checks completed"
}

# Function to display service information
display_service_info() {
    print_status "Service Information:"
    echo
    
    echo "Query Engines:"
    kubectl get services --namespace "$NAMESPACE_QUERY_ENGINES"
    echo
    
    echo "Monitoring:"
    kubectl get services --namespace "$NAMESPACE_MONITORING"
    echo
    
    echo "Pods Status:"
    kubectl get pods --namespace "$NAMESPACE_QUERY_ENGINES"
    echo
    
    kubectl get pods --namespace "$NAMESPACE_MONITORING"
    echo
    
    print_status "Access URLs:"
    echo "  - Presto Coordinator: http://presto-coordinator.$NAMESPACE_QUERY_ENGINES.svc.cluster.local:8080"
    echo "  - ClickHouse: http://clickhouse.$NAMESPACE_QUERY_ENGINES.svc.cluster.local:8123"
    echo "  - Prometheus: http://prometheus.$NAMESPACE_MONITORING.svc.cluster.local:9090"
    echo "  - Grafana: http://grafana.$NAMESPACE_MONITORING.svc.cluster.local:3000"
    echo "  - Chaos Mesh Dashboard: http://chaos-mesh-controller-manager.$NAMESPACE_CHAOS.svc.cluster.local:2333"
}

# Function to apply Chaos Mesh experiments
apply_chaos_experiments() {
    print_status "Applying Chaos Mesh experiments..."
    
    kubectl apply -f ../fault-tests/chaos-mesh/chaos-experiments.yaml
    
    print_success "Chaos experiments applied"
}

# Main deployment function
main() {
    print_status "Starting distributed query engine deployment..."
    
    # Check prerequisites
    check_prerequisites
    
    # Check cluster connectivity
    check_cluster
    
    # Create namespaces
    create_namespaces
    
    # Deploy components
    deploy_monitoring
    deploy_spark_operator
    deploy_clickhouse
    deploy_presto
    deploy_chaos_mesh
    
    # Verify deployments
    verify_deployments
    
    # Run health checks
    run_health_checks
    
    # Apply chaos experiments
    apply_chaos_experiments
    
    # Display service information
    display_service_info
    
    print_success "Deployment completed successfully!"
    print_status "You can now run benchmarks and fault injection tests."
}

# Function to clean up
cleanup() {
    print_status "Cleaning up deployments..."
    
    # Delete Chaos Mesh experiments
    kubectl delete -f ../fault-tests/chaos-mesh/chaos-experiments.yaml --ignore-not-found=true
    
    # Delete Helm releases
    helm uninstall presto --namespace "$NAMESPACE_QUERY_ENGINES" --ignore-not-found=true
    helm uninstall clickhouse --namespace "$NAMESPACE_QUERY_ENGINES" --ignore-not-found=true
    helm uninstall spark-operator --namespace "$NAMESPACE_QUERY_ENGINES" --ignore-not-found=true
    helm uninstall monitoring --namespace "$NAMESPACE_MONITORING" --ignore-not-found=true
    helm uninstall chaos-mesh --namespace "$NAMESPACE_CHAOS" --ignore-not-found=true
    
    # Delete namespaces
    kubectl delete namespace "$NAMESPACE_QUERY_ENGINES" --ignore-not-found=true
    kubectl delete namespace "$NAMESPACE_MONITORING" --ignore-not-found=true
    kubectl delete namespace "$NAMESPACE_CHAOS" --ignore-not-found=true
    
    print_success "Cleanup completed"
}

# Parse command line arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "cleanup")
        cleanup
        ;;
    "verify")
        verify_deployments
        ;;
    "health")
        run_health_checks
        ;;
    *)
        echo "Usage: $0 {deploy|cleanup|verify|health}"
        echo "  deploy  - Deploy all components (default)"
        echo "  cleanup - Remove all deployments"
        echo "  verify  - Verify deployment status"
        echo "  health  - Run health checks"
        exit 1
        ;;
esac
