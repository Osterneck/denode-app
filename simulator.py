import logging
from sqlalchemy import create_engine, text
import re

logger = logging.getLogger(__name__)

def run_explain(connection_url, query, analyze=True, buffers=True, verbose=False):
    """
    Run EXPLAIN on a query to analyze its performance characteristics.
    
    Args:
        connection_url (str): SQLAlchemy connection URL
        query (str): SQL query to analyze
        analyze (bool): Whether to run ANALYZE with EXPLAIN (actual execution)
        buffers (bool): Whether to include buffer statistics
        verbose (bool): Whether to get verbose output
        
    Returns:
        dict: Parsed EXPLAIN output with performance metrics
    """
    try:
        # Detect database type from connection URL to adapt EXPLAIN syntax
        db_type = 'unknown'
        if 'postgresql' in connection_url or 'postgres' in connection_url:
            db_type = 'postgresql'
        elif 'mysql' in connection_url:
            db_type = 'mysql'
        elif 'sqlite' in connection_url:
            db_type = 'sqlite'
        
        engine = create_engine(connection_url)
        
        # Construct appropriate EXPLAIN command based on database type
        explain_query = ""
        if db_type == 'postgresql':
            options = []
            if analyze:
                options.append("ANALYZE")
            if buffers:
                options.append("BUFFERS")
            if verbose:
                options.append("VERBOSE")
            
            options_str = ", ".join(options)
            explain_query = f"EXPLAIN ({options_str}) {query}"
        
        elif db_type == 'mysql':
            explain_query = f"EXPLAIN{'ANALYZE ' if analyze else ' '}{query}"
        
        elif db_type == 'sqlite':
            explain_query = f"EXPLAIN QUERY PLAN {query}"
        
        else:
            explain_query = f"EXPLAIN {query}"
        
        logger.debug(f"Running explain query: {explain_query}")
        
        # Execute the EXPLAIN query
        with engine.connect() as conn:
            result = conn.execute(text(explain_query))
            explain_output = result.fetchall()
        
        # Parse the results based on database type
        parsed_result = parse_explain_output(explain_output, db_type)
        
        return parsed_result
    
    except Exception as e:
        logger.error(f"Error running EXPLAIN: {str(e)}")
        return {"error": str(e)}

def parse_explain_output(explain_output, db_type):
    """
    Parse the EXPLAIN output based on database type.
    
    Args:
        explain_output (list): Raw EXPLAIN results
        db_type (str): Database type (postgresql, mysql, sqlite)
        
    Returns:
        dict: Structured performance metrics
    """
    result = {
        "steps": [],
        "metrics": {}
    }
    
    if db_type == 'postgresql':
        # Parse PostgreSQL EXPLAIN output
        full_text = '\n'.join([str(row[0]) for row in explain_output])
        
        # Extract planning and execution time if available
        planning_time = re.search(r'Planning Time: ([0-9.]+)', full_text)
        execution_time = re.search(r'Execution Time: ([0-9.]+)', full_text)
        
        if planning_time:
            result["metrics"]["planning_time_ms"] = float(planning_time.group(1))
        if execution_time:
            result["metrics"]["execution_time_ms"] = float(execution_time.group(1))
        
        # Look for sequential scans (potential optimization target)
        seq_scans = re.findall(r'Seq Scan on ([^\s]+)', full_text)
        if seq_scans:
            result["metrics"]["sequential_scans"] = seq_scans
        
        # Look for index scans (good performance indicator)
        index_scans = re.findall(r'Index Scan using ([^\s]+)', full_text)
        if index_scans:
            result["metrics"]["index_scans"] = index_scans
        
        # Check for hash joins (memory intensive)
        hash_joins = len(re.findall(r'Hash Join', full_text))
        if hash_joins > 0:
            result["metrics"]["hash_joins"] = hash_joins
        
        # Check for merge joins (good for sorted data)
        merge_joins = len(re.findall(r'Merge Join', full_text))
        if merge_joins > 0:
            result["metrics"]["merge_joins"] = merge_joins
    
    elif db_type == 'mysql':
        # Parse MySQL EXPLAIN output
        result["steps"] = [dict(row) for row in explain_output]
        
        # Look for full table scans
        full_scans = [row for row in result["steps"] if row.get("type") == "ALL"]
        if full_scans:
            result["metrics"]["full_table_scans"] = len(full_scans)
        
        # Look for index usage
        index_usage = [row for row in result["steps"] if "index" in str(row.get("type")).lower()]
        if index_usage:
            result["metrics"]["index_usage"] = len(index_usage)
    
    elif db_type == 'sqlite':
        # Parse SQLite EXPLAIN output
        result["steps"] = [{"id": row[0], "parent": row[1], "detail": row[3]} for row in explain_output]
        
        # Look for scans
        scans = [row["detail"] for row in result["steps"] if "SCAN" in row["detail"]]
        result["metrics"]["scan_operations"] = len(scans)
        
        # Look for search operations
        searches = [row["detail"] for row in result["steps"] if "SEARCH" in row["detail"]]
        result["metrics"]["search_operations"] = len(searches)
    
    # Add original explain output
    result["raw_output"] = explain_output
    
    return result

def simulate_performance(connection_url, queries, schema=None):
    """
    Simulate performance for a set of queries.
    
    Args:
        connection_url (str): SQLAlchemy connection URL
        queries (list): List of query strings to analyze
        schema (dict, optional): Schema information for context
        
    Returns:
        dict: Performance analysis for each query
    """
    results = {}
    
    for i, query in enumerate(queries):
        query_key = f"query_{i+1}"
        try:
            # Run explain on the query
            explain_result = run_explain(connection_url, query)
            
            # Add basic performance score
            performance_score = calculate_performance_score(explain_result)
            
            results[query_key] = {
                "query": query,
                "explain_result": explain_result,
                "performance_score": performance_score
            }
            
        except Exception as e:
            logger.error(f"Error simulating performance for query {i+1}: {str(e)}")
            results[query_key] = {
                "query": query,
                "error": str(e)
            }
    
    return results

def calculate_performance_score(explain_result):
    """
    Calculate a simple performance score based on EXPLAIN results.
    Lower is better.
    
    Args:
        explain_result (dict): Parsed EXPLAIN output
        
    Returns:
        float: Performance score
    """
    score = 50  # Start with a baseline score
    
    metrics = explain_result.get("metrics", {})
    
    # Adjust score based on execution time if available
    if "execution_time_ms" in metrics:
        exec_time = metrics["execution_time_ms"]
        if exec_time < 10:
            score -= 20
        elif exec_time < 50:
            score -= 10
        elif exec_time > 500:
            score += 30
        elif exec_time > 1000:
            score += 50
    
    # Penalize sequential scans
    if "sequential_scans" in metrics:
        score += len(metrics["sequential_scans"]) * 15
    
    # Reward index usage
    if "index_scans" in metrics:
        score -= len(metrics["index_scans"]) * 10
    
    # Adjust for join types
    if "hash_joins" in metrics:
        score += metrics["hash_joins"] * 5  # Small penalty for hash joins
    
    if "merge_joins" in metrics:
        score -= metrics["merge_joins"] * 5  # Small bonus for merge joins
    
    # Ensure score is within reasonable bounds
    score = max(0, min(100, score))
    
    return score
