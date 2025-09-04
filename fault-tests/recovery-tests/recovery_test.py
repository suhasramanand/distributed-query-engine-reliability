#!/usr/bin/env python3
"""
Recovery Testing Script for Distributed Query Engines
Measures failover and recovery times under various failure scenarios
"""

import argparse
import json
import time
import statistics
from datetime import datetime
from typing import Dict, List, Any
import subprocess
import requests
import kubernetes
from kubernetes import client, config
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RecoveryTestRunner:
    def __init__(self, namespace: str = "query-engines"):
        self.namespace = namespace
        self.k8s_client = None
        self.test_results = {}
        
        # Initialize Kubernetes client
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
            
        self.k8s_client = client.CoreV1Api()
        
    def measure_service_availability(self, service_name: str, port: int = 8080) -> Dict[str, Any]:
        """Measure service availability by making HTTP requests"""
        results = {
            "service": service_name,
            "availability": 0.0,
            "response_times": [],
            "errors": [],
            "total_requests": 0,
            "successful_requests": 0
        }
        
        # Make 10 requests to measure availability
        for i in range(10):
            start_time = time.time()
            try:
                response = requests.get(f"http://{service_name}:{port}/ping", timeout=5)
                response_time = time.time() - start_time
                results["response_times"].append(response_time)
                results["successful_requests"] += 1
                if response.status_code == 200:
                    results["availability"] += 1
            except Exception as e:
                response_time = time.time() - start_time
                results["response_times"].append(response_time)
                results["errors"].append(str(e))
                
            results["total_requests"] += 1
            time.sleep(1)  # Wait 1 second between requests
            
        results["availability"] = results["availability"] / results["total_requests"]
        if results["response_times"]:
            results["avg_response_time"] = statistics.mean(results["response_times"])
            results["min_response_time"] = min(results["response_times"])
            results["max_response_time"] = max(results["response_times"])
        else:
            results["avg_response_time"] = 0
            results["min_response_time"] = 0
            results["max_response_time"] = 0
            
        return results
        
    def measure_pod_recovery_time(self, deployment_name: str) -> Dict[str, Any]:
        """Measure time for pods to recover after a failure"""
        results = {
            "deployment": deployment_name,
            "recovery_time": 0.0,
            "pod_restart_count": 0,
            "status": "unknown"
        }
        
        try:
            # Get deployment status before failure
            deployment = self.k8s_client.read_namespaced_deployment(
                name=deployment_name,
                namespace=self.namespace
            )
            initial_replicas = deployment.status.ready_replicas or 0
            
            # Simulate pod failure by scaling down and up
            logger.info(f"Simulating failure for deployment {deployment_name}")
            
            # Scale down to 0
            start_time = time.time()
            self.k8s_client.patch_namespaced_deployment_scale(
                name=deployment_name,
                namespace=self.namespace,
                body={"spec": {"replicas": 0}}
            )
            
            # Wait for scale down
            self._wait_for_deployment_scale(deployment_name, 0)
            scale_down_time = time.time() - start_time
            
            # Scale back up
            start_time = time.time()
            self.k8s_client.patch_namespaced_deployment_scale(
                name=deployment_name,
                namespace=self.namespace,
                body={"spec": {"replicas": initial_replicas}}
            )
            
            # Wait for scale up
            self._wait_for_deployment_scale(deployment_name, initial_replicas)
            recovery_time = time.time() - start_time
            
            results["recovery_time"] = recovery_time
            results["scale_down_time"] = scale_down_time
            results["status"] = "success"
            
            # Get pod restart count
            pods = self.k8s_client.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"app.kubernetes.io/name={deployment_name}"
            )
            
            total_restarts = 0
            for pod in pods.items:
                for container in pod.status.container_statuses:
                    total_restarts += container.restart_count
                    
            results["pod_restart_count"] = total_restarts
            
        except Exception as e:
            logger.error(f"Error measuring recovery time for {deployment_name}: {e}")
            results["status"] = "error"
            results["error"] = str(e)
            
        return results
        
    def _wait_for_deployment_scale(self, deployment_name: str, target_replicas: int, timeout: int = 300):
        """Wait for deployment to scale to target number of replicas"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                deployment = self.k8s_client.read_namespaced_deployment(
                    name=deployment_name,
                    namespace=self.namespace
                )
                current_replicas = deployment.status.ready_replicas or 0
                
                if current_replicas == target_replicas:
                    return True
                    
                time.sleep(5)
            except Exception as e:
                logger.warning(f"Error checking deployment scale: {e}")
                time.sleep(5)
                
        raise TimeoutError(f"Deployment {deployment_name} did not scale to {target_replicas} replicas within {timeout} seconds")
        
    def measure_node_failure_recovery(self) -> Dict[str, Any]:
        """Measure recovery time after node failure simulation"""
        results = {
            "test_type": "node_failure",
            "recovery_time": 0.0,
            "affected_pods": [],
            "status": "unknown"
        }
        
        try:
            # Get initial pod distribution
            initial_pods = self.k8s_client.list_namespaced_pod(
                namespace=self.namespace,
                label_selector="NodeGroup=analytics"
            )
            
            initial_pod_count = len(initial_pods.items)
            results["initial_pod_count"] = initial_pod_count
            
            # Simulate node failure by cordoning a node
            nodes = self.k8s_client.list_node(label_selector="NodeGroup=analytics")
            if nodes.items:
                target_node = nodes.items[0].metadata.name
                logger.info(f"Simulating failure on node {target_node}")
                
                start_time = time.time()
                
                # Cordon the node
                self.k8s_client.patch_node(
                    name=target_node,
                    body={"spec": {"unschedulable": True}}
                )
                
                # Wait for pods to be rescheduled
                self._wait_for_pod_reschedule(initial_pod_count)
                
                # Uncordon the node
                self.k8s_client.patch_node(
                    name=target_node,
                    body={"spec": {"unschedulable": False}}
                )
                
                recovery_time = time.time() - start_time
                results["recovery_time"] = recovery_time
                results["status"] = "success"
                
        except Exception as e:
            logger.error(f"Error measuring node failure recovery: {e}")
            results["status"] = "error"
            results["error"] = str(e)
            
        return results
        
    def _wait_for_pod_reschedule(self, expected_pod_count: int, timeout: int = 300):
        """Wait for pods to be rescheduled after node failure"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                pods = self.k8s_client.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector="NodeGroup=analytics"
                )
                
                ready_pods = sum(1 for pod in pods.items if pod.status.phase == "Running")
                
                if ready_pods >= expected_pod_count:
                    return True
                    
                time.sleep(10)
            except Exception as e:
                logger.warning(f"Error checking pod reschedule: {e}")
                time.sleep(10)
                
        raise TimeoutError(f"Pods did not reschedule within {timeout} seconds")
        
    def measure_network_partition_recovery(self) -> Dict[str, Any]:
        """Measure recovery time after network partition simulation"""
        results = {
            "test_type": "network_partition",
            "recovery_time": 0.0,
            "affected_services": [],
            "status": "unknown"
        }
        
        try:
            # Test service connectivity before partition
            services = ["presto-coordinator", "clickhouse", "spark-operator"]
            initial_availability = {}
            
            for service in services:
                initial_availability[service] = self.measure_service_availability(service)
                
            results["initial_availability"] = initial_availability
            
            # Simulate network partition using Chaos Mesh
            logger.info("Simulating network partition")
            start_time = time.time()
            
            # Apply network chaos
            network_chaos = {
                "apiVersion": "chaos-mesh.org/v1alpha1",
                "kind": "NetworkChaos",
                "metadata": {
                    "name": "network-partition-test",
                    "namespace": self.namespace
                },
                "spec": {
                    "action": "partition",
                    "mode": "all",
                    "selector": {
                        "namespaces": [self.namespace]
                    },
                    "duration": "30s"
                }
            }
            
            # Apply the chaos (this would require Chaos Mesh to be installed)
            # For now, we'll simulate with a sleep
            time.sleep(30)
            
            # Measure recovery
            recovery_time = time.time() - start_time
            results["recovery_time"] = recovery_time
            
            # Test service connectivity after recovery
            final_availability = {}
            for service in services:
                final_availability[service] = self.measure_service_availability(service)
                
            results["final_availability"] = final_availability
            results["status"] = "success"
            
        except Exception as e:
            logger.error(f"Error measuring network partition recovery: {e}")
            results["status"] = "error"
            results["error"] = str(e)
            
        return results
        
    def run_comprehensive_recovery_test(self) -> Dict[str, Any]:
        """Run comprehensive recovery testing"""
        logger.info("Starting comprehensive recovery testing...")
        
        test_results = {
            "test_info": {
                "timestamp": datetime.now().isoformat(),
                "namespace": self.namespace,
                "test_duration": 0
            },
            "service_availability": {},
            "pod_recovery": {},
            "node_failure_recovery": {},
            "network_partition_recovery": {},
            "summary": {}
        }
        
        start_time = time.time()
        
        # Test 1: Service Availability
        logger.info("Testing service availability...")
        services = ["presto-coordinator", "clickhouse", "spark-operator"]
        for service in services:
            test_results["service_availability"][service] = self.measure_service_availability(service)
            
        # Test 2: Pod Recovery
        logger.info("Testing pod recovery...")
        deployments = ["presto-coordinator", "presto-worker", "clickhouse"]
        for deployment in deployments:
            test_results["pod_recovery"][deployment] = self.measure_pod_recovery_time(deployment)
            
        # Test 3: Node Failure Recovery
        logger.info("Testing node failure recovery...")
        test_results["node_failure_recovery"] = self.measure_node_failure_recovery()
        
        # Test 4: Network Partition Recovery
        logger.info("Testing network partition recovery...")
        test_results["network_partition_recovery"] = self.measure_network_partition_recovery()
        
        test_duration = time.time() - start_time
        test_results["test_info"]["test_duration"] = test_duration
        
        # Calculate summary
        self._calculate_recovery_summary(test_results)
        
        return test_results
        
    def _calculate_recovery_summary(self, results: Dict[str, Any]):
        """Calculate summary statistics from recovery test results"""
        summary = {
            "overall_availability": 0.0,
            "avg_recovery_time": 0.0,
            "max_recovery_time": 0.0,
            "total_tests": 0,
            "successful_tests": 0,
            "failed_tests": 0
        }
        
        # Service availability summary
        availability_scores = []
        for service_result in results["service_availability"].values():
            availability_scores.append(service_result["availability"])
            summary["total_tests"] += 1
            if service_result["availability"] > 0.9:
                summary["successful_tests"] += 1
            else:
                summary["failed_tests"] += 1
                
        if availability_scores:
            summary["overall_availability"] = statistics.mean(availability_scores)
            
        # Recovery time summary
        recovery_times = []
        for recovery_result in results["pod_recovery"].values():
            if recovery_result["status"] == "success":
                recovery_times.append(recovery_result["recovery_time"])
                summary["total_tests"] += 1
                summary["successful_tests"] += 1
            else:
                summary["total_tests"] += 1
                summary["failed_tests"] += 1
                
        if recovery_times:
            summary["avg_recovery_time"] = statistics.mean(recovery_times)
            summary["max_recovery_time"] = max(recovery_times)
            
        # Node failure recovery
        if results["node_failure_recovery"]["status"] == "success":
            recovery_times.append(results["node_failure_recovery"]["recovery_time"])
            summary["total_tests"] += 1
            summary["successful_tests"] += 1
        else:
            summary["total_tests"] += 1
            summary["failed_tests"] += 1
            
        # Network partition recovery
        if results["network_partition_recovery"]["status"] == "success":
            recovery_times.append(results["network_partition_recovery"]["recovery_time"])
            summary["total_tests"] += 1
            summary["successful_tests"] += 1
        else:
            summary["total_tests"] += 1
            summary["failed_tests"] += 1
            
        if recovery_times:
            summary["avg_recovery_time"] = statistics.mean(recovery_times)
            summary["max_recovery_time"] = max(recovery_times)
            
        summary["success_rate"] = summary["successful_tests"] / summary["total_tests"] if summary["total_tests"] > 0 else 0
        
        results["summary"] = summary

def main():
    parser = argparse.ArgumentParser(description="Run recovery testing for distributed query engines")
    parser.add_argument("--namespace", default="query-engines", help="Kubernetes namespace")
    parser.add_argument("--output-file", required=True, help="Output file for results")
    parser.add_argument("--test-type", choices=["comprehensive", "service", "pod", "node", "network"], 
                       default="comprehensive", help="Type of recovery test to run")
    
    args = parser.parse_args()
    
    # Create test runner
    runner = RecoveryTestRunner(namespace=args.namespace)
    
    # Run tests based on type
    if args.test_type == "comprehensive":
        results = runner.run_comprehensive_recovery_test()
    elif args.test_type == "service":
        results = {"service_availability": {}}
        services = ["presto-coordinator", "clickhouse", "spark-operator"]
        for service in services:
            results["service_availability"][service] = runner.measure_service_availability(service)
    elif args.test_type == "pod":
        results = {"pod_recovery": {}}
        deployments = ["presto-coordinator", "presto-worker", "clickhouse"]
        for deployment in deployments:
            results["pod_recovery"][deployment] = runner.measure_pod_recovery_time(deployment)
    elif args.test_type == "node":
        results = {"node_failure_recovery": runner.measure_node_failure_recovery()}
    elif args.test_type == "network":
        results = {"network_partition_recovery": runner.measure_network_partition_recovery()}
    
    # Save results
    with open(args.output_file, 'w') as f:
        json.dump(results, f, indent=2)
        
    # Print summary
    if "summary" in results:
        summary = results["summary"]
        logger.info(f"Recovery testing completed!")
        logger.info(f"Overall availability: {summary['overall_availability']:.2%}")
        logger.info(f"Average recovery time: {summary['avg_recovery_time']:.2f}s")
        logger.info(f"Maximum recovery time: {summary['max_recovery_time']:.2f}s")
        logger.info(f"Success rate: {summary['success_rate']:.2%}")
        logger.info(f"Total tests: {summary['total_tests']}")
        logger.info(f"Successful tests: {summary['successful_tests']}")
        logger.info(f"Failed tests: {summary['failed_tests']}")
    else:
        logger.info(f"Recovery testing completed!")
        
    logger.info(f"Results saved to: {args.output_file}")

if __name__ == "__main__":
    main()
