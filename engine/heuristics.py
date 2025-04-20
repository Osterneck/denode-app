import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

def recommend_changes(schema, query_analysis, performance_data=None):
    """
    Generate schema optimization recommendations based on query patterns and performance.
    
    Args:
        schema (dict): Database schema from schema_extractor
        query_analysis (dict): Query analysis from query_log_analyzer
        performance_data (dict, optional): Performance metrics from simulator
        
    Returns:
        list: List of recommendations with rationale
    """
    recommendations = []
    
    # Track table stats
    table_stats = defaultdict(dict)
    
    # Process tables for denormalization candidates
    for table_name, metrics in query_analysis.get("table_metrics", {}).items():
        if table_name not in schema:
            continue
            
        # Extract key metrics
        join_count = metrics.get("join_count", 0)
        normalization_score = metrics.get("normalization_score", 0)
        access_count = metrics.get("access_count", 0)
        
        # Calculate read/write ratio from query data
        read_count = query_analysis.get("query_counts", {}).get("select", 0)
        write_count = sum([
            query_analysis.get("query_counts", {}).get("insert", 0),
            query_analysis.get("query_counts", {}).get("update", 0),
            query_analysis.get("query_counts", {}).get("delete", 0)
        ])
        read_write_ratio = read_count / max(write_count, 1)
        
        # Store computed metrics
        table_stats[table_name] = {
            "join_count": join_count,
            "normalization_score": normalization_score,
            "access_count": access_count,
            "read_write_ratio": read_write_ratio,
            "column_count": schema[table_name].get("column_count", 0),
            "foreign_keys": len(schema[table_name].get("foreign_keys", [])),
            "has_performance_data": table_name in (performance_data or {})
        }
    
    # Apply heuristics for denormalization
    for table_name, stats in table_stats.items():
        # High join frequency and mostly read-only tables are good denormalization candidates
        if (stats["join_count"] > 3 and 
            stats["read_write_ratio"] > 5 and 
            stats["access_count"] > 5):
            
            # Look for related tables through foreign keys
            related_tables = []
            for fk in schema[table_name].get("foreign_keys", []):
                referred_table = fk.get("referred_table")
                if referred_table in table_stats:
                    related_tables.append(referred_table)
            
            if related_tables:
                recommendations.append({
                    "table": table_name,
                    "action": "DENORMALIZE",
                    "related_tables": related_tables,
                    "confidence": min(95, 50 + stats["join_count"] * 5 + stats["read_write_ratio"]),
                    "reason": (
                        f"Table '{table_name}' is frequently joined ({stats['join_count']} joins), "
                        f"has a high read/write ratio ({stats['read_write_ratio']:.1f}), and "
                        f"is commonly accessed ({stats['access_count']} accesses). "
                        f"Consider denormalizing with {', '.join(related_tables)}."
                    )
                })
    
    # Apply heuristics for normalization
    for table_name, stats in table_stats.items():
        # Tables with many columns and low join activity might need normalization
        if (stats["column_count"] > 15 and 
            stats["join_count"] < 2 and 
            stats["foreign_keys"] < 2):
            
            recommendations.append({
                "table": table_name,
                "action": "NORMALIZE",
                "confidence": min(90, 40 + stats["column_count"] * 2),
                "reason": (
                    f"Table '{table_name}' has many columns ({stats['column_count']}), "
                    f"but low join activity ({stats['join_count']} joins) and few foreign keys "
                    f"({stats['foreign_keys']}). Consider normalizing this table by extracting "
                    f"related attributes into separate tables."
                )
            })
    
    # Apply heuristics for indexing
    if performance_data:
        for query_key, perf_data in performance_data.items():
            explain_result = perf_data.get("explain_result", {})
            metrics = explain_result.get("metrics", {})
            
            # Look for sequential scans, which might benefit from indexing
            seq_scans = metrics.get("sequential_scans", [])
            for table in seq_scans:
                if table in schema:
                    recommendations.append({
                        "table": table,
                        "action": "INDEX",
                        "confidence": 80,
                        "reason": (
                            f"Table '{table}' is being sequentially scanned in query: "
                            f"{perf_data.get('query', '')}. Consider adding an index on relevant columns."
                        )
                    })
    
    # Apply heuristics for partitioning large tables
    for table_name, stats in table_stats.items():
        if table_name in schema and stats["access_count"] > 10:
            # Check if table has a date/timestamp column that could be used for partitioning
            has_date_column = False
            for col in schema[table_name].get("columns", []):
                col_type = col.get("type", "").lower()
                if "date" in col_type or "time" in col_type:
                    has_date_column = True
                    break
            
            if has_date_column and stats["read_write_ratio"] > 3:
                recommendations.append({
                    "table": table_name,
                    "action": "PARTITION",
                    "confidence": 70,
                    "reason": (
                        f"Table '{table_name}' is frequently accessed ({stats['access_count']} times) "
                        f"and has date/time columns. Consider partitioning this table to improve query "
                        f"performance on time-based data."
                    )
                })
    
    # Sort recommendations by confidence
    recommendations.sort(key=lambda x: x["confidence"], reverse=True)
    
    logger.info(f"Generated {len(recommendations)} recommendations")
    return recommendations
