import re
import os
import logging
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)

def parse_query_logs(log_path):
    """
    Parse SQL query logs to identify patterns and frequencies.
    
    Args:
        log_path (str): Path to the query log file
        
    Returns:
        dict: Dictionary with query classification and statistics
    """
    if not os.path.exists(log_path):
        logger.error(f"Log file not found: {log_path}")
        raise FileNotFoundError(f"Log file not found: {log_path}")
    
    try:
        with open(log_path, 'r') as f:
            logs = f.read().splitlines()
        
        # Filter out empty lines and comments
        logs = [line.strip() for line in logs if line.strip() and not line.strip().startswith('--')]
        
        # Extract and classify queries
        joins = [line for line in logs if re.search(r'\bJOIN\b', line, re.IGNORECASE)]
        selects = [line for line in logs if re.search(r'\bSELECT\b', line, re.IGNORECASE)]
        inserts = [line for line in logs if re.search(r'\bINSERT\b', line, re.IGNORECASE)]
        updates = [line for line in logs if re.search(r'\bUPDATE\b', line, re.IGNORECASE)]
        deletes = [line for line in logs if re.search(r'\bDELETE\b', line, re.IGNORECASE)]
        
        # Extract tables involved in queries
        table_pattern = r'(?:FROM|JOIN|INTO|UPDATE)\s+([a-zA-Z0-9_]+)'
        tables_involved = []
        for line in logs:
            tables = re.findall(table_pattern, line, re.IGNORECASE)
            tables_involved.extend(tables)
        
        # Count table occurrences and build table relationships
        table_counts = Counter(tables_involved)
        
        # Identify columns frequently used in WHERE clauses
        where_pattern = r'WHERE\s+([^;]+)'
        where_conditions = []
        for line in logs:
            matches = re.findall(where_pattern, line, re.IGNORECASE)
            where_conditions.extend(matches)
        
        # Count join types
        inner_joins = len([j for j in joins if re.search(r'INNER\s+JOIN', j, re.IGNORECASE) or 
                          (re.search(r'JOIN', j, re.IGNORECASE) and not re.search(r'(LEFT|RIGHT|FULL|OUTER)\s+JOIN', j, re.IGNORECASE))])
        left_joins = len([j for j in joins if re.search(r'LEFT\s+JOIN', j, re.IGNORECASE)])
        right_joins = len([j for j in joins if re.search(r'RIGHT\s+JOIN', j, re.IGNORECASE)])
        
        # Compute read/write ratio
        read_count = len(selects)
        write_count = len(inserts) + len(updates) + len(deletes)
        read_write_ratio = read_count / max(write_count, 1)  # Avoid division by zero
        
        # Build the comprehensive result
        result = {
            "query_counts": {
                "select": len(selects),
                "insert": len(inserts),
                "update": len(updates),
                "delete": len(deletes),
                "total": len(logs)
            },
            "join_analysis": {
                "total_joins": len(joins),
                "inner_joins": inner_joins,
                "left_joins": left_joins,
                "right_joins": right_joins
            },
            "table_access": dict(table_counts),
            "read_write_ratio": read_write_ratio,
            "examples": {
                "joins": joins[:5] if joins else [],
                "selects": selects[:5] if selects else [],
                "inserts": inserts[:5] if inserts else [],
                "updates": updates[:5] if updates else []
            }
        }
        
        logger.info(f"Analyzed {len(logs)} queries")
        return result
    
    except Exception as e:
        logger.error(f"Error parsing query logs: {str(e)}")
        raise

def analyze_query_patterns(query_data, schema):
    """
    Analyze query patterns to identify optimization opportunities.
    
    Args:
        query_data (dict): Query analysis data from parse_query_logs
        schema (dict): Database schema from schema_extractor
        
    Returns:
        dict: Advanced analytics with optimization hints
    """
    analytics = {
        "table_metrics": {},
        "join_patterns": [],
        "normalized_scores": {}
    }
    
    # Calculate metrics for each table
    for table_name, access_count in query_data["table_access"].items():
        if table_name in schema:
            table_info = schema[table_name]
            col_count = table_info["column_count"]
            index_count = len(table_info["indexes"])
            foreign_key_count = len(table_info["foreign_keys"])
            
            # Calculate a "normalization score" based on table structure
            # Higher score suggests more normalized table
            normalization_score = min(10, (foreign_key_count * 2) + (index_count) - (col_count / 10))
            
            analytics["table_metrics"][table_name] = {
                "access_count": access_count,
                "column_count": col_count,
                "index_count": index_count,
                "foreign_key_count": foreign_key_count,
                "normalization_score": normalization_score
            }
            
            analytics["normalized_scores"][table_name] = normalization_score
    
    # Calculate join complexity
    join_count = query_data["join_analysis"]["total_joins"]
    tables_with_joins = []
    
    for join in query_data.get("examples", {}).get("joins", []):
        for table_name in schema.keys():
            if re.search(r'\b' + table_name + r'\b', join, re.IGNORECASE):
                tables_with_joins.append(table_name)
    
    tables_with_joins_counter = Counter(tables_with_joins)
    for table, count in tables_with_joins_counter.items():
        if table in analytics["table_metrics"]:
            analytics["table_metrics"][table]["join_count"] = count
            
            # Add to the join patterns list
            analytics["join_patterns"].append({
                "table": table,
                "join_frequency": count,
                "percentage": count / max(join_count, 1) * 100
            })
    
    return analytics
