#!/usr/bin/env python3
"""
TPC-H Benchmark Runner for Presto/Trino
"""

import argparse
import json
import time
import statistics
from datetime import datetime
from typing import Dict, List, Any
import requests
from presto import PrestoConnection
import pandas as pd
from tqdm import tqdm
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# TPC-H Queries
TPCH_QUERIES = {
    "Q1": """
    SELECT
        l_returnflag,
        l_linestatus,
        sum(l_quantity) as sum_qty,
        sum(l_extendedprice) as sum_base_price,
        sum(l_extendedprice * (1 - l_discount)) as sum_disc_price,
        sum(l_extendedprice * (1 - l_discount) * (1 + l_tax)) as sum_charge,
        avg(l_quantity) as avg_qty,
        avg(l_extendedprice) as avg_price,
        avg(l_discount) as avg_disc,
        count(*) as count_order
    FROM lineitem
    WHERE l_shipdate <= DATE '1998-12-01' - INTERVAL '90' DAY
    GROUP BY l_returnflag, l_linestatus
    ORDER BY l_returnflag, l_linestatus
    """,
    
    "Q2": """
    SELECT
        s_acctbal,
        s_name,
        n_name,
        p_partkey,
        p_mfgr,
        s_address,
        s_phone,
        s_comment
    FROM part, supplier, partsupp, nation, region
    WHERE p_partkey = ps_partkey
        AND s_suppkey = ps_suppkey
        AND p_size = 15
        AND p_type LIKE '%BRASS'
        AND s_nationkey = n_nationkey
        AND n_regionkey = r_regionkey
        AND r_name = 'EUROPE'
        AND ps_supplycost = (
            SELECT min(ps_supplycost)
            FROM partsupp, supplier, nation, region
            WHERE p_partkey = ps_partkey
                AND s_suppkey = ps_suppkey
                AND s_nationkey = n_nationkey
                AND n_regionkey = r_regionkey
                AND r_name = 'EUROPE'
        )
    ORDER BY s_acctbal DESC, n_name, s_name, p_partkey
    """,
    
    "Q3": """
    SELECT
        l_orderkey,
        sum(l_extendedprice * (1 - l_discount)) as revenue,
        o_orderdate,
        o_shippriority
    FROM customer, orders, lineitem
    WHERE c_mktsegment = 'BUILDING'
        AND c_custkey = o_custkey
        AND l_orderkey = o_orderkey
        AND o_orderdate < DATE '1995-03-15'
        AND l_shipdate > DATE '1995-03-15'
    GROUP BY l_orderkey, o_orderdate, o_shippriority
    ORDER BY revenue DESC, o_orderdate
    """,
    
    "Q4": """
    SELECT
        o_orderpriority,
        count(*) as order_count
    FROM orders
    WHERE o_orderdate >= DATE '1993-07-01'
        AND o_orderdate < DATE '1993-07-01' + INTERVAL '3' MONTH
        AND EXISTS (
            SELECT *
            FROM lineitem
            WHERE l_orderkey = o_orderkey
                AND l_commitdate < l_receiptdate
        )
    GROUP BY o_orderpriority
    ORDER BY o_orderpriority
    """,
    
    "Q5": """
    SELECT
        n_name,
        sum(l_extendedprice * (1 - l_discount)) as revenue
    FROM customer, orders, lineitem, supplier, nation, region
    WHERE c_custkey = o_custkey
        AND l_orderkey = o_orderkey
        AND l_suppkey = s_suppkey
        AND c_nationkey = s_nationkey
        AND s_nationkey = n_nationkey
        AND n_regionkey = r_regionkey
        AND r_name = 'ASIA'
        AND o_orderdate >= DATE '1994-01-01'
        AND o_orderdate < DATE '1994-01-01' + INTERVAL '1' YEAR
    GROUP BY n_name
    ORDER BY revenue DESC
    """,
    
    "Q6": """
    SELECT
        sum(l_extendedprice * l_discount) as revenue
    FROM lineitem
    WHERE l_shipdate >= DATE '1994-01-01'
        AND l_shipdate < DATE '1994-01-01' + INTERVAL '1' YEAR
        AND l_discount BETWEEN 0.06 - 0.01 AND 0.06 + 0.01
        AND l_quantity < 24
    """,
    
    "Q7": """
    SELECT
        supp_nation,
        cust_nation,
        l_year,
        sum(volume) as revenue
    FROM (
        SELECT
            n1.n_name as supp_nation,
            n2.n_name as cust_nation,
            extract(year from l_shipdate) as l_year,
            l_extendedprice * (1 - l_discount) as volume
        FROM supplier, lineitem, orders, customer, nation n1, nation n2
        WHERE s_suppkey = l_suppkey
            AND o_orderkey = l_orderkey
            AND c_custkey = o_custkey
            AND s_nationkey = n1.n_nationkey
            AND c_nationkey = n2.n_nationkey
            AND (
                (n1.n_name = 'FRANCE' AND n2.n_name = 'GERMANY')
                OR (n1.n_name = 'GERMANY' AND n2.n_name = 'FRANCE')
            )
            AND l_shipdate BETWEEN DATE '1995-01-01' AND DATE '1996-12-31'
    ) as shipping
    GROUP BY supp_nation, cust_nation, l_year
    ORDER BY supp_nation, cust_nation, l_year
    """,
    
    "Q8": """
    SELECT
        o_year,
        sum(case when nation = 'BRAZIL' then volume else 0 end) / sum(volume) as mkt_share
    FROM (
        SELECT
            extract(year from o_orderdate) as o_year,
            l_extendedprice * (1 - l_discount) as volume,
            n2.n_name as nation
        FROM part, supplier, lineitem, orders, customer, nation n1, nation n2, region
        WHERE p_partkey = l_partkey
            AND s_suppkey = l_suppkey
            AND l_orderkey = o_orderkey
            AND o_custkey = c_custkey
            AND c_nationkey = n1.n_nationkey
            AND n1.n_regionkey = r_regionkey
            AND r_name = 'AMERICA'
            AND s_nationkey = n2.n_nationkey
            AND o_orderdate BETWEEN DATE '1995-01-01' AND DATE '1996-12-31'
            AND p_type = 'ECONOMY ANODIZED STEEL'
    ) as all_nations
    GROUP BY o_year
    ORDER BY o_year
    """,
    
    "Q9": """
    SELECT
        nation,
        o_year,
        sum(amount) as sum_profit
    FROM (
        SELECT
            n_name as nation,
            extract(year from o_orderdate) as o_year,
            l_extendedprice * (1 - l_discount) - ps_supplycost * l_quantity as amount
        FROM part, supplier, lineitem, partsupp, orders, nation
        WHERE s_suppkey = l_suppkey
            AND ps_suppkey = l_suppkey
            AND ps_partkey = l_partkey
            AND p_partkey = l_partkey
            AND o_orderkey = l_orderkey
            AND s_nationkey = n_nationkey
            AND p_name LIKE '%green%'
    ) as profit
    GROUP BY nation, o_year
    ORDER BY nation, o_year DESC
    """,
    
    "Q10": """
    SELECT
        c_custkey,
        c_name,
        sum(l_extendedprice * (1 - l_discount)) as revenue,
        c_acctbal,
        n_name,
        c_address,
        c_phone,
        c_comment
    FROM customer, orders, lineitem, nation
    WHERE c_custkey = o_custkey
        AND l_orderkey = o_orderkey
        AND o_orderdate >= DATE '1993-10-01'
        AND o_orderdate < DATE '1993-10-01' + INTERVAL '3' MONTH
        AND l_returnflag = 'R'
        AND c_nationkey = n_nationkey
    GROUP BY c_custkey, c_name, c_acctbal, c_phone, n_name, c_address, c_comment
    ORDER BY revenue DESC
    """,
    
    "Q11": """
    SELECT
        ps_partkey,
        sum(ps_supplycost * ps_availqty) as value
    FROM partsupp, supplier, nation
    WHERE ps_suppkey = s_suppkey
        AND s_nationkey = n_nationkey
        AND n_name = 'GERMANY'
    GROUP BY ps_partkey
    HAVING sum(ps_supplycost * ps_availqty) > (
        SELECT sum(ps_supplycost * ps_availqty) * 0.0001000000
        FROM partsupp, supplier, nation
        WHERE ps_suppkey = s_suppkey
            AND s_nationkey = n_nationkey
            AND n_name = 'GERMANY'
    )
    ORDER BY value DESC
    """,
    
    "Q12": """
    SELECT
        l_shipmode,
        sum(case when o_orderpriority = '1-URGENT' or o_orderpriority = '2-HIGH' then 1 else 0 end) as high_line_count,
        sum(case when o_orderpriority <> '1-URGENT' and o_orderpriority <> '2-HIGH' then 1 else 0 end) as low_line_count
    FROM orders, lineitem
    WHERE o_orderkey = l_orderkey
        AND l_shipmode IN ('MAIL', 'SHIP')
        AND l_commitdate < l_receiptdate
        AND l_shipdate < l_commitdate
        AND l_receiptdate >= DATE '1994-01-01'
        AND l_receiptdate < DATE '1994-01-01' + INTERVAL '1' YEAR
    GROUP BY l_shipmode
    ORDER BY l_shipmode
    """,
    
    "Q13": """
    SELECT
        c_count,
        count(*) as custdist
    FROM (
        SELECT
            c_custkey,
            count(o_orderkey) as c_count
        FROM customer left outer join orders on c_custkey = o_custkey and o_comment not like '%special%requests%'
        GROUP BY c_custkey
    ) as c_orders
    GROUP BY c_count
    ORDER BY custdist DESC, c_count DESC
    """,
    
    "Q14": """
    SELECT
        100.00 * sum(case when p_type like 'PROMO%' then l_extendedprice * (1 - l_discount) else 0 end) / sum(l_extendedprice * (1 - l_discount)) as promo_revenue
    FROM lineitem, part
    WHERE l_partkey = p_partkey
        AND l_shipdate >= DATE '1995-09-01'
        AND l_shipdate < DATE '1995-09-01' + INTERVAL '1' MONTH
    """,
    
    "Q15": """
    SELECT
        s_suppkey,
        s_name,
        s_address,
        s_phone,
        total_revenue
    FROM supplier, revenue0
    WHERE s_suppkey = supplier_no
        AND total_revenue = (
            SELECT max(total_revenue)
            FROM revenue0
        )
    ORDER BY s_suppkey
    """,
    
    "Q16": """
    SELECT
        p_brand,
        p_type,
        p_size,
        count(distinct ps_suppkey) as supplier_cnt
    FROM partsupp, part
    WHERE p_partkey = ps_partkey
        AND p_brand <> 'Brand#45'
        AND p_type not like 'MEDIUM POLISHED%'
        AND p_size IN (49, 14, 23, 45, 19, 3, 36, 9)
        AND ps_suppkey not IN (
            SELECT s_suppkey
            FROM supplier
            WHERE s_comment like '%Customer%Complaints%'
        )
    GROUP BY p_brand, p_type, p_size
    ORDER BY supplier_cnt DESC, p_brand, p_type, p_size
    """,
    
    "Q17": """
    SELECT
        sum(l_extendedprice) / 7.0 as avg_yearly
    FROM lineitem, part
    WHERE p_partkey = l_partkey
        AND p_brand = 'Brand#23'
        AND p_container = 'MED BOX'
        AND l_quantity < (
            SELECT 0.2 * avg(l_quantity)
            FROM lineitem
            WHERE l_partkey = p_partkey
        )
    """,
    
    "Q18": """
    SELECT
        c_name,
        c_custkey,
        o_orderkey,
        o_orderdate,
        o_totalprice,
        sum(l_quantity)
    FROM customer, orders, lineitem
    WHERE o_orderkey in (
        SELECT l_orderkey
        FROM lineitem
        GROUP BY l_orderkey
        HAVING sum(l_quantity) > 300
    )
        AND c_custkey = o_custkey
        AND o_orderkey = l_orderkey
    GROUP BY c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice
    ORDER BY o_totalprice DESC, o_orderdate
    """,
    
    "Q19": """
    SELECT
        sum(l_extendedprice * (1 - l_discount)) as revenue
    FROM lineitem, part
    WHERE (
        p_partkey = l_partkey
        AND p_brand = 'Brand#12'
        AND p_container IN ('SM CASE', 'SM BOX', 'SM PACK', 'SM PKG')
        AND l_quantity >= 1 and l_quantity <= 11
        AND p_size BETWEEN 1 AND 5
        AND l_shipmode IN ('AIR', 'AIR REG')
        AND l_shipinstruct = 'DELIVER IN PERSON'
    )
    OR (
        p_partkey = l_partkey
        AND p_brand = 'Brand#23'
        AND p_container IN ('MED BAG', 'MED BOX', 'MED PKG', 'MED PACK')
        AND l_quantity >= 10 and l_quantity <= 20
        AND p_size BETWEEN 1 AND 10
        AND l_shipmode IN ('AIR', 'AIR REG')
        AND l_shipinstruct = 'DELIVER IN PERSON'
    )
    OR (
        p_partkey = l_partkey
        AND p_brand = 'Brand#34'
        AND p_container IN ('LG CASE', 'LG BOX', 'LG PACK', 'LG PKG')
        AND l_quantity >= 20 and l_quantity <= 30
        AND p_size BETWEEN 1 AND 15
        AND l_shipmode IN ('AIR', 'AIR REG')
        AND l_shipinstruct = 'DELIVER IN PERSON'
    )
    """,
    
    "Q20": """
    SELECT
        s_name,
        s_address
    FROM supplier, nation
    WHERE s_suppkey in (
        SELECT ps_suppkey
        FROM partsupp
        WHERE ps_partkey in (
            SELECT p_partkey
            FROM part
            WHERE p_name like 'forest%'
        )
        AND ps_availqty > (
            SELECT 0.5 * sum(l_quantity)
            FROM lineitem
            WHERE l_partkey = ps_partkey
                AND l_suppkey = ps_suppkey
                AND l_shipdate >= DATE '1994-01-01'
                AND l_shipdate < DATE '1994-01-01' + INTERVAL '1' YEAR
        )
    )
        AND s_nationkey = n_nationkey
        AND n_name = 'CANADA'
    ORDER BY s_name
    """,
    
    "Q21": """
    SELECT
        s_name,
        count(*) as numwait
    FROM supplier, lineitem l1, orders, nation
    WHERE s_suppkey = l1.l_suppkey
        AND o_orderkey = l1.l_orderkey
        AND o_orderstatus = 'F'
        AND l1.l_receiptdate > l1.l_commitdate
        AND EXISTS (
            SELECT *
            FROM lineitem l2
            WHERE l2.l_orderkey = l1.l_orderkey
                AND l2.l_suppkey <> l1.l_suppkey
        )
        AND NOT EXISTS (
            SELECT *
            FROM lineitem l3
            WHERE l3.l_orderkey = l1.l_orderkey
                AND l3.l_suppkey <> l1.l_suppkey
                AND l3.l_receiptdate > l3.l_commitdate
        )
        AND s_nationkey = n_nationkey
        AND n_name = 'SAUDI ARABIA'
    GROUP BY s_name
    ORDER BY numwait DESC, s_name
    """,
    
    "Q22": """
    SELECT
        cntrycode,
        count(*) as numcust,
        sum(c_acctbal) as totacctbal
    FROM (
        SELECT
            substring(c_phone from 1 for 2) as cntrycode,
            c_acctbal
        FROM customer
        WHERE substring(c_phone from 1 for 2) in (
            '13', '31', '23', '29', '30', '18', '17'
        )
        AND c_acctbal > (
            SELECT avg(c_acctbal)
            FROM customer
            WHERE c_acctbal > 0.00
                AND substring(c_phone from 1 for 2) in (
                    '13', '31', '23', '29', '30', '18', '17'
                )
        )
        AND NOT EXISTS (
            SELECT *
            FROM orders
            WHERE o_custkey = c_custkey
        )
    ) as custsale
    GROUP BY cntrycode
    ORDER BY cntrycode
    """
}

class PrestoBenchmarkRunner:
    def __init__(self, host: str, port: int, catalog: str, schema: str, user: str = "benchmark"):
        self.host = host
        self.port = port
        self.catalog = catalog
        self.schema = schema
        self.user = user
        self.connection = None
        
    def connect(self):
        """Establish connection to Presto"""
        try:
            self.connection = PrestoConnection(
                host=self.host,
                port=self.port,
                catalog=self.catalog,
                schema=self.schema,
                user=self.user
            )
            logger.info(f"Connected to Presto at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Presto: {e}")
            raise
            
    def execute_query(self, query: str, query_name: str) -> Dict[str, Any]:
        """Execute a single query and return timing information"""
        start_time = time.time()
        try:
            cursor = self.connection.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            execution_time = time.time() - start_time
            
            return {
                "query_name": query_name,
                "execution_time": execution_time,
                "row_count": len(results),
                "status": "success",
                "error": None
            }
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Query {query_name} failed: {e}")
            return {
                "query_name": query_name,
                "execution_time": execution_time,
                "row_count": 0,
                "status": "error",
                "error": str(e)
            }
            
    def run_benchmark(self, iterations: int = 3, warmup_runs: int = 1) -> Dict[str, Any]:
        """Run the complete TPC-H benchmark"""
        if not self.connection:
            self.connect()
            
        results = {
            "benchmark_info": {
                "name": "TPC-H Benchmark",
                "engine": "Presto/Trino",
                "timestamp": datetime.now().isoformat(),
                "iterations": iterations,
                "warmup_runs": warmup_runs,
                "total_queries": len(TPCH_QUERIES)
            },
            "queries": {},
            "summary": {}
        }
        
        # Warmup runs
        logger.info(f"Running {warmup_runs} warmup iterations...")
        for i in range(warmup_runs):
            for query_name, query in TPCH_QUERIES.items():
                self.execute_query(query, f"warmup_{query_name}")
                
        # Actual benchmark runs
        logger.info(f"Running {iterations} benchmark iterations...")
        for iteration in tqdm(range(iterations), desc="Benchmark iterations"):
            iteration_results = {}
            
            for query_name, query in TPCH_QUERIES.items():
                result = self.execute_query(query, query_name)
                iteration_results[query_name] = result
                
            results["queries"][f"iteration_{iteration}"] = iteration_results
            
        # Calculate summary statistics
        self._calculate_summary(results, iterations)
        
        return results
        
    def _calculate_summary(self, results: Dict[str, Any], iterations: int):
        """Calculate summary statistics from benchmark results"""
        query_stats = {}
        
        for query_name in TPCH_QUERIES.keys():
            execution_times = []
            success_count = 0
            error_count = 0
            
            for i in range(iterations):
                iteration_key = f"iteration_{i}"
                if iteration_key in results["queries"]:
                    query_result = results["queries"][iteration_key][query_name]
                    if query_result["status"] == "success":
                        execution_times.append(query_result["execution_time"])
                        success_count += 1
                    else:
                        error_count += 1
                        
            if execution_times:
                query_stats[query_name] = {
                    "avg_execution_time": statistics.mean(execution_times),
                    "min_execution_time": min(execution_times),
                    "max_execution_time": max(execution_times),
                    "std_execution_time": statistics.stdev(execution_times) if len(execution_times) > 1 else 0,
                    "success_count": success_count,
                    "error_count": error_count,
                    "success_rate": success_count / (success_count + error_count)
                }
            else:
                query_stats[query_name] = {
                    "avg_execution_time": 0,
                    "min_execution_time": 0,
                    "max_execution_time": 0,
                    "std_execution_time": 0,
                    "success_count": 0,
                    "error_count": error_count,
                    "success_rate": 0
                }
                
        # Overall summary
        all_execution_times = []
        total_success = 0
        total_errors = 0
        
        for stats in query_stats.values():
            if stats["success_count"] > 0:
                all_execution_times.extend([stats["avg_execution_time"]] * stats["success_count"])
            total_success += stats["success_count"]
            total_errors += stats["error_count"]
            
        results["summary"] = {
            "query_statistics": query_stats,
            "overall": {
                "total_queries_executed": total_success + total_errors,
                "successful_queries": total_success,
                "failed_queries": total_errors,
                "overall_success_rate": total_success / (total_success + total_errors) if (total_success + total_errors) > 0 else 0,
                "avg_execution_time": statistics.mean(all_execution_times) if all_execution_times else 0,
                "total_execution_time": sum(all_execution_times) if all_execution_times else 0,
                "queries_per_second": total_success / sum(all_execution_times) if all_execution_times else 0
            }
        }

def main():
    parser = argparse.ArgumentParser(description="Run TPC-H benchmarks on Presto/Trino")
    parser.add_argument("--presto-host", required=True, help="Presto coordinator host")
    parser.add_argument("--presto-port", type=int, default=8080, help="Presto coordinator port")
    parser.add_argument("--catalog", default="hive", help="Presto catalog")
    parser.add_argument("--schema", default="tpch", help="Presto schema")
    parser.add_argument("--user", default="benchmark", help="Presto user")
    parser.add_argument("--iterations", type=int, default=3, help="Number of benchmark iterations")
    parser.add_argument("--warmup-runs", type=int, default=1, help="Number of warmup runs")
    parser.add_argument("--output-file", required=True, help="Output file for results")
    
    args = parser.parse_args()
    
    # Create benchmark runner
    runner = PrestoBenchmarkRunner(
        host=args.presto_host,
        port=args.presto_port,
        catalog=args.catalog,
        schema=args.schema,
        user=args.user
    )
    
    # Run benchmark
    logger.info("Starting TPC-H benchmark...")
    results = runner.run_benchmark(
        iterations=args.iterations,
        warmup_runs=args.warmup_runs
    )
    
    # Save results
    with open(args.output_file, 'w') as f:
        json.dump(results, f, indent=2)
        
    # Print summary
    summary = results["summary"]["overall"]
    logger.info(f"Benchmark completed!")
    logger.info(f"Total queries executed: {summary['total_queries_executed']}")
    logger.info(f"Successful queries: {summary['successful_queries']}")
    logger.info(f"Failed queries: {summary['failed_queries']}")
    logger.info(f"Success rate: {summary['overall_success_rate']:.2%}")
    logger.info(f"Average execution time: {summary['avg_execution_time']:.2f}s")
    logger.info(f"Queries per second: {summary['queries_per_second']:.2f}")
    logger.info(f"Results saved to: {args.output_file}")

if __name__ == "__main__":
    main()
