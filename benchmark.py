"""
Performance Benchmarking Module for DEnode

This module provides tools for quickly benchmarking database performance:
- Query execution timing
- Resource utilization measurement
- Comparison of different optimization strategies
"""

import time
import logging
import statistics
from sqlalchemy import create_engine, text
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("denode-benchmark")

class PerformanceBenchmark:
    """
    Database performance benchmarking utility that measures:
    - Query execution time
    - Query throughput
    - Resource utilization
    """
    
    def __init__(self, connection_url):
        """
        Initialize the performance benchmark tool.
        
        Args:
            connection_url (str): SQLAlchemy connection URL
        """
        self.connection_url = connection_url
        self.engine = create_engine(connection_url)
        self.results = {}
        
    def time_query(self, query, iterations=5, warmup=1):
        """
        Measure the execution time of a query.
        
        Args:
            query (str): SQL query to benchmark
            iterations (int): Number of times to run the query for averaging
            warmup (int): Number of warmup runs (not counted in results)
            
        Returns:
            dict: Timing statistics (min, max, avg, median)
        """
        logger.info(f"Benchmarking query performance with {iterations} iterations")
        
        execution_times = []
        
        with self.engine.connect() as conn:
            # Warmup runs
            for _ in range(warmup):
                conn.execute(text(query))
                
            # Timed runs
            for i in range(iterations):
                start_time = time.time()
                conn.execute(text(query))
                end_time = time.time()
                execution_time = (end_time - start_time) * 1000  # Convert to ms
                execution_times.append(execution_time)
                logger.debug(f"Run {i+1}: {execution_time:.2f}ms")
        
        # Calculate statistics
        stats = {
            "min": min(execution_times),
            "max": max(execution_times),
            "avg": statistics.mean(execution_times),
            "median": statistics.median(execution_times),
            "stdev": statistics.stdev(execution_times) if len(execution_times) > 1 else 0,
            "iterations": iterations,
            "unit": "ms"
        }
        
        return stats
    
    def run_throughput_test(self, query, duration=5, concurrent_clients=5):
        """
        Test query throughput under concurrent load.
        
        Args:
            query (str): SQL query to benchmark
            duration (int): Test duration in seconds
            concurrent_clients (int): Number of simultaneous clients
            
        Returns:
            dict: Throughput statistics
        """
        logger.info(f"Running throughput test with {concurrent_clients} concurrent clients for {duration}s")
        
        results = []
        stop_time = time.time() + duration
        
        def run_client(client_id):
            """Run queries for a single client until time expires"""
            client_count = 0
            client_times = []
            
            with self.engine.connect() as conn:
                while time.time() < stop_time:
                    start_time = time.time()
                    conn.execute(text(query))
                    end_time = time.time()
                    client_times.append((end_time - start_time) * 1000)  # Convert to ms
                    client_count += 1
                    
            return {
                "client_id": client_id,
                "queries_executed": client_count,
                "execution_times": client_times
            }
        
        # Run concurrent clients
        with ThreadPoolExecutor(max_workers=concurrent_clients) as executor:
            futures = [executor.submit(run_client, i) for i in range(concurrent_clients)]
            for future in futures:
                results.append(future.result())
        
        # Aggregate results
        total_queries = sum(r["queries_executed"] for r in results)
        all_times = [t for r in results for t in r["execution_times"]]
        
        throughput_stats = {
            "queries_per_second": total_queries / duration,
            "total_queries": total_queries,
            "concurrent_clients": concurrent_clients,
            "duration_seconds": duration,
            "avg_latency_ms": statistics.mean(all_times) if all_times else 0,
            "median_latency_ms": statistics.median(all_times) if all_times else 0,
            "min_latency_ms": min(all_times) if all_times else 0,
            "max_latency_ms": max(all_times) if all_times else 0
        }
        
        return throughput_stats
    
    def compare_queries(self, queries, iterations=3):
        """
        Compare the performance of multiple queries.
        
        Args:
            queries (dict): Dictionary of query name to query string
            iterations (int): Number of iterations for each query
            
        Returns:
            dict: Comparison results for each query
        """
        logger.info(f"Comparing performance of {len(queries)} queries")
        
        comparison = {}
        
        for name, query in queries.items():
            comparison[name] = self.time_query(query, iterations=iterations)
            
        return comparison
    
    def benchmark_schema_change(self, before_query, after_query, iterations=3):
        """
        Benchmark the performance impact of a schema change.
        
        Args:
            before_query (str): Query to benchmark with original schema
            after_query (str): Query to benchmark with modified schema
            iterations (int): Number of iterations for each query
            
        Returns:
            dict: Performance comparison before and after
        """
        before_stats = self.time_query(before_query, iterations=iterations)
        after_stats = self.time_query(after_query, iterations=iterations)
        
        improvement = (before_stats["avg"] - after_stats["avg"]) / before_stats["avg"] * 100
        
        return {
            "before": before_stats,
            "after": after_stats,
            "percent_improvement": improvement,
            "absolute_improvement_ms": before_stats["avg"] - after_stats["avg"]
        }

def create_sample_data(connection_url, table_name, row_count):
    """
    Create sample data for benchmarking.
    
    Args:
        connection_url (str): SQLAlchemy connection URL
        table_name (str): Table name to create
        row_count (int): Number of rows to generate
        
    Returns:
        bool: Success flag
    """
    engine = create_engine(connection_url)
    
    with engine.connect() as conn:
        # Drop table if exists
        conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
        
        # Create table
        conn.execute(text(
            f"""
            CREATE TABLE {table_name} (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                value INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))
        
        # Insert data in batches
        batch_size = 1000
        for i in range(0, row_count, batch_size):
            batch_end = min(i + batch_size, row_count)
            values = []
            for j in range(i, batch_end):
                values.append(f"('name_{j}', {j % 100})")
            
            values_str = ", ".join(values)
            conn.execute(text(
                f"""
                INSERT INTO {table_name} (name, value)
                VALUES {values_str}
                """
            ))
    
    return True