import logging

logger = logging.getLogger(__name__)

def generate_sql(recommendation, schema):
    """
    Generate SQL statements to implement the recommended changes.
    
    Args:
        recommendation (dict): Recommendation details from recommend_changes
        schema (dict): Database schema information
        
    Returns:
        dict: SQL implementation plan with statements and explanation
    """
    table = recommendation.get("table")
    action = recommendation.get("action")
    
    if not table or not action or table not in schema:
        logger.warning(f"Invalid recommendation: {recommendation}")
        return {"error": "Invalid recommendation"}
    
    sql_plan = {
        "table": table,
        "action": action,
        "statements": [],
        "explanation": "",
        "caution": ""
    }
    
    if action == "DENORMALIZE":
        sql_plan = generate_denormalization_sql(recommendation, schema)
    elif action == "NORMALIZE":
        sql_plan = generate_normalization_sql(recommendation, schema)
    elif action == "INDEX":
        sql_plan = generate_index_sql(recommendation, schema)
    elif action == "PARTITION":
        sql_plan = generate_partition_sql(recommendation, schema)
    
    logger.info(f"Generated SQL plan for {action} on table {table}")
    return sql_plan

def generate_denormalization_sql(recommendation, schema):
    """
    Generate SQL for denormalization operations.
    
    Args:
        recommendation (dict): Recommendation details
        schema (dict): Database schema information
        
    Returns:
        dict: SQL plan for denormalization
    """
    table = recommendation.get("table")
    related_tables = recommendation.get("related_tables", [])
    
    plan = {
        "table": table,
        "action": "DENORMALIZE",
        "statements": [],
        "explanation": "This plan creates a denormalized view/table that combines data from related tables.",
        "caution": "Denormalization may increase storage requirements and make updates more complex."
    }
    
    if not related_tables:
        plan["error"] = "No related tables specified for denormalization"
        return plan
    
    # Get table structure
    table_columns = [col["name"] for col in schema[table].get("columns", [])]
    
    # Create a view first (safer approach)
    view_name = f"{table}_denormalized_view"
    select_columns = [f"{table}.{col}" for col in table_columns]
    join_clauses = []
    
    # Build SELECT and JOIN clauses for each related table
    for related_table in related_tables:
        if related_table not in schema:
            continue
            
        # Find foreign key relationship
        fk_found = False
        for fk in schema[table].get("foreign_keys", []):
            if fk.get("referred_table") == related_table:
                fk_found = True
                constrained_columns = fk.get("constrained_columns", [])
                referred_columns = fk.get("referred_columns", [])
                
                if constrained_columns and referred_columns:
                    join_condition = " AND ".join([
                        f"{table}.{const_col} = {related_table}.{ref_col}" 
                        for const_col, ref_col in zip(constrained_columns, referred_columns)
                    ])
                    
                    join_clauses.append(f"LEFT JOIN {related_table} ON {join_condition}")
                    
                    # Add columns from related table (excluding the join key)
                    related_columns = [
                        col["name"] for col in schema[related_table].get("columns", [])
                        if col["name"] not in referred_columns
                    ]
                    
                    for col in related_columns:
                        select_columns.append(f"{related_table}.{col} AS {related_table}_{col}")
                    
                    break
        
        if not fk_found:
            # Try reverse relationship
            for fk in schema[related_table].get("foreign_keys", []):
                if fk.get("referred_table") == table:
                    constrained_columns = fk.get("constrained_columns", [])
                    referred_columns = fk.get("referred_columns", [])
                    
                    if constrained_columns and referred_columns:
                        join_condition = " AND ".join([
                            f"{related_table}.{const_col} = {table}.{ref_col}" 
                            for const_col, ref_col in zip(constrained_columns, referred_columns)
                        ])
                        
                        join_clauses.append(f"LEFT JOIN {related_table} ON {join_condition}")
                        
                        # Add columns from related table
                        related_columns = [
                            col["name"] for col in schema[related_table].get("columns", [])
                            if col["name"] not in constrained_columns
                        ]
                        
                        for col in related_columns:
                            select_columns.append(f"{related_table}.{col} AS {related_table}_{col}")
                        
                        break
    
    # Create view SQL
    if join_clauses:
        columns_str = ",\n    ".join(select_columns)
        joins_str = "\n    ".join(join_clauses)
        
        view_sql = f"""CREATE OR REPLACE VIEW {view_name} AS
SELECT
    {columns_str}
FROM
    {table}
    {joins_str};"""
        
        plan["statements"].append({
            "type": "view",
            "name": view_name,
            "sql": view_sql
        })
        
        # Also provide materialized view/table option
        mat_view_name = f"{table}_denormalized"
        mat_view_sql = f"""CREATE TABLE {mat_view_name} AS
SELECT * FROM {view_name};

-- Create indexes on frequently queried columns
CREATE INDEX idx_{mat_view_name}_id ON {mat_view_name} (id);
"""
        
        plan["statements"].append({
            "type": "materialized",
            "name": mat_view_name,
            "sql": mat_view_sql
        })
        
        # Explain the approach
        plan["explanation"] = f"""
This plan creates:
1. A view ({view_name}) that joins {table} with {', '.join(related_tables)}
2. A materialized table option ({mat_view_name}) for better query performance
3. Recommended indexes on the materialized table

The view preserves data integrity while the materialized table offers better read performance.
"""
    else:
        plan["error"] = "Could not determine join relationships between tables"
    
    return plan

def generate_normalization_sql(recommendation, schema):
    """
    Generate SQL for normalization operations.
    
    Args:
        recommendation (dict): Recommendation details
        schema (dict): Database schema information
        
    Returns:
        dict: SQL plan for normalization
    """
    table = recommendation.get("table")
    
    plan = {
        "table": table,
        "action": "NORMALIZE",
        "statements": [],
        "explanation": "This plan extracts related columns into new tables to normalize the schema.",
        "caution": "Normalization requires data migration and application changes."
    }
    
    # Analyze columns to identify potential groupings
    columns = schema[table].get("columns", [])
    column_names = [col["name"] for col in columns]
    
    # Look for column naming patterns that suggest related data
    prefixes = {}
    for col_name in column_names:
        parts = col_name.split('_')
        if len(parts) > 1:
            prefix = parts[0]
            if prefix not in prefixes:
                prefixes[prefix] = []
            prefixes[prefix].append(col_name)
    
    # Filter prefixes with multiple columns (potential candidates for extraction)
    extraction_candidates = {prefix: cols for prefix, cols in prefixes.items() if len(cols) > 1}
    
    # Generate SQL for each candidate group
    for prefix, cols in extraction_candidates.items():
        if len(cols) < 2:  # Need at least 2 columns to make normalization worthwhile
            continue
            
        # Create new table
        new_table_name = f"{table}_{prefix}"
        id_column = f"{new_table_name}_id"
        
        # Generate CREATE TABLE statement
        column_defs = [f"{id_column} SERIAL PRIMARY KEY"]
        for col in cols:
            # Get column type from original schema
            col_type = next((c["type"] for c in columns if c["name"] == col), "VARCHAR(255)")
            column_defs.append(f"{col} {col_type}")
        
        column_def_str = ',\n    '.join(column_defs)
        create_table_sql = f"""CREATE TABLE {new_table_name} (
    {column_def_str}
);"""
        
        # Add foreign key to original table
        alter_table_sql = f"""ALTER TABLE {table} 
ADD COLUMN {id_column} INTEGER,
ADD CONSTRAINT fk_{table}_{new_table_name} 
FOREIGN KEY ({id_column}) REFERENCES {new_table_name}({id_column});"""
        
        # Data migration - create new records and link to original table
        migration_sql = f"""-- Step 1: Insert distinct combinations into new table
INSERT INTO {new_table_name} ({', '.join(cols)})
SELECT DISTINCT {', '.join(cols)} FROM {table};

-- Step 2: Update foreign keys in original table
UPDATE {table} t
SET {id_column} = nt.{id_column}
FROM {new_table_name} nt
WHERE {' AND '.join([f't.{col} = nt.{col}' for col in cols])};

-- Step 3: Remove redundant columns from original table
ALTER TABLE {table}
{', '.join([f'DROP COLUMN {col}' for col in cols])};"""
        
        plan["statements"].append({
            "type": "create_table",
            "name": new_table_name,
            "sql": create_table_sql
        })
        
        plan["statements"].append({
            "type": "alter_table",
            "name": table,
            "sql": alter_table_sql
        })
        
        plan["statements"].append({
            "type": "data_migration",
            "tables": [table, new_table_name],
            "sql": migration_sql
        })
    
    if not plan["statements"]:
        # Fallback if no clear patterns found
        plan["explanation"] = "No clear column groupings found for normalization. Consider manual schema review."
    else:
        plan["explanation"] = f"""
The normalization plan:
1. Creates {len(extraction_candidates)} new tables to extract related columns
2. Adds foreign keys to the original table
3. Migrates data to maintain relationships
4. Removes redundant columns from the original table

This plan is based on column naming patterns suggesting related data.
"""
    
    return plan

def generate_index_sql(recommendation, schema):
    """
    Generate SQL for index creation.
    
    Args:
        recommendation (dict): Recommendation details
        schema (dict): Database schema information
        
    Returns:
        dict: SQL plan for indexing
    """
    table = recommendation.get("table")
    
    plan = {
        "table": table,
        "action": "INDEX",
        "statements": [],
        "explanation": "This plan adds indexes to improve query performance.",
        "caution": "Indexes improve read performance but may slow down writes."
    }
    
    # Check existing indexes
    existing_indexes = schema[table].get("indexes", [])
    existing_indexed_columns = set()
    for idx in existing_indexes:
        for col in idx.get("column_names", []):
            existing_indexed_columns.add(col)
    
    # Get columns from the table
    columns = schema[table].get("columns", [])
    
    # Identify potential index candidates
    pk_columns = set()
    for col in columns:
        if col.get("is_primary_key", False):
            pk_columns.add(col["name"])
    
    # Check foreign key columns
    fk_columns = set()
    for fk in schema[table].get("foreign_keys", []):
        for col in fk.get("constrained_columns", []):
            fk_columns.add(col)
    
    # Generate index candidates - focus on foreign keys and potential filter columns
    index_candidates = []
    
    # Foreign key indexes (if not already indexed)
    for col in fk_columns:
        if col not in existing_indexed_columns and col not in pk_columns:
            index_candidates.append({
                "name": f"idx_{table}_{col}",
                "columns": [col],
                "reason": "Foreign key column"
            })
    
    # Look for potential date/time columns
    for col in columns:
        col_name = col["name"]
        col_type = str(col["type"]).lower()
        
        if (col_name not in existing_indexed_columns and
            col_name not in pk_columns and
            ("date" in col_type or "time" in col_type)):
            index_candidates.append({
                "name": f"idx_{table}_{col_name}",
                "columns": [col_name],
                "reason": "Date/time column (common in filters/sorting)"
            })
    
    # Look for status, type, category columns
    status_cols = []
    for col in columns:
        col_name = col["name"].lower()
        if (col["name"] not in existing_indexed_columns and
            col["name"] not in pk_columns and
            ("status" in col_name or "type" in col_name or "category" in col_name) and
            ("char" in str(col["type"]).lower() or "varchar" in str(col["type"]).lower())):
            status_cols.append(col["name"])
            index_candidates.append({
                "name": f"idx_{table}_{col['name']}",
                "columns": [col["name"]],
                "reason": "Status/type/category column (common in filters)"
            })
    
    # Generate SQL statements
    for candidate in index_candidates:
        columns_str = ", ".join(candidate["columns"])
        index_sql = f"""CREATE INDEX {candidate["name"]} ON {table} ({columns_str});
-- {candidate["reason"]}"""
        
        plan["statements"].append({
            "type": "index",
            "name": candidate["name"],
            "sql": index_sql
        })
    
    if not plan["statements"]:
        plan["explanation"] = "No additional indexes recommended. Existing indexes appear sufficient."
    else:
        plan["explanation"] = f"""
Recommended {len(plan["statements"])} new indexes for table '{table}':
{"".join([f"- {stmt['name']}: {', '.join(index_candidates[i]['columns'])} ({index_candidates[i]['reason']})" for i, stmt in enumerate(plan["statements"])])}

These indexes target foreign keys and columns commonly used in WHERE clauses or joins.
"""
    
    return plan

def generate_partition_sql(recommendation, schema):
    """
    Generate SQL for table partitioning.
    
    Args:
        recommendation (dict): Recommendation details
        schema (dict): Database schema information
        
    Returns:
        dict: SQL plan for partitioning
    """
    table = recommendation.get("table")
    
    plan = {
        "table": table,
        "action": "PARTITION",
        "statements": [],
        "explanation": "This plan implements table partitioning for better performance on large tables.",
        "caution": "Partitioning requires careful planning and may need application changes."
    }
    
    # Find date/time columns for partitioning
    columns = schema[table].get("columns", [])
    partition_column = None
    
    for col in columns:
        col_name = col["name"]
        col_type = str(col["type"]).lower()
        
        if "date" in col_type or "time" in col_type:
            partition_column = col_name
            break
    
    if not partition_column:
        plan["error"] = "No suitable date/time column found for partitioning"
        return plan
    
    # Generate SQL for PostgreSQL partitioning
    # Get all columns for new table creation
    column_defs = []
    for col in columns:
        nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
        default = f"DEFAULT {col['default']}" if col.get("default") and col["default"] != "None" else ""
        column_defs.append(f"{col['name']} {col['type']} {nullable} {default}".strip())
    
    new_table_name = f"{table}_partitioned"
    column_def_str = ',\n    '.join(column_defs)
    partition_sql = f"""-- Step 1: Create new partitioned table
CREATE TABLE {new_table_name} (
    {column_def_str}
) PARTITION BY RANGE ({partition_column});

-- Step 2: Create initial partitions (adjust ranges as needed)
CREATE TABLE {new_table_name}_p2023_q1 PARTITION OF {new_table_name}
    FOR VALUES FROM ('2023-01-01') TO ('2023-04-01');
    
CREATE TABLE {new_table_name}_p2023_q2 PARTITION OF {new_table_name}
    FOR VALUES FROM ('2023-04-01') TO ('2023-07-01');
    
CREATE TABLE {new_table_name}_p2023_q3 PARTITION OF {new_table_name}
    FOR VALUES FROM ('2023-07-01') TO ('2023-10-01');
    
CREATE TABLE {new_table_name}_p2023_q4 PARTITION OF {new_table_name}
    FOR VALUES FROM ('2023-10-01') TO ('2024-01-01');

-- Step 3: Create indexes on partitioned table
CREATE INDEX idx_{new_table_name}_{partition_column} ON {new_table_name} ({partition_column});

-- Step 4: Migrate data from original table
INSERT INTO {new_table_name} SELECT * FROM {table};

-- Step 5: Rename tables to swap them
ALTER TABLE {table} RENAME TO {table}_old;
ALTER TABLE {new_table_name} RENAME TO {table};

-- Step 6: Create a function to manage partitions
CREATE OR REPLACE FUNCTION manage_{table}_partitions()
RETURNS VOID AS $$
DECLARE
    next_quarter DATE;
BEGIN
    -- Calculate the next quarter date
    SELECT date_trunc('quarter', now()) + interval '3 months' INTO next_quarter;
    
    -- Create a new partition if it doesn't exist
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %s_p%s PARTITION OF %s
         FOR VALUES FROM (%L) TO (%L)',
        '{table}',
        to_char(next_quarter, 'YYYY_Q'),
        '{table}',
        next_quarter,
        next_quarter + interval '3 months'
    );
END;
$$ LANGUAGE plpgsql;

-- Step 7: Create a trigger to run the partition management function
CREATE EXTENSION IF NOT EXISTS pg_cron;

SELECT cron.schedule('0 0 1 * *', 'SELECT manage_" + table + "_partitions()');
"""
    
    plan["statements"].append({
        "type": "partition",
        "name": table,
        "sql": partition_sql
    })
    
    plan["explanation"] = f"""
This partitioning plan:
1. Creates a new table partitioned by the '{partition_column}' column
2. Sets up initial quarterly partitions
3. Migrates data from the original table
4. Renames tables to preserve the original name
5. Creates a maintenance function and schedule to automatically add future partitions

Partitioning works best for tables with time-series data and queries that filter on the partition column.
"""
    
    return plan
