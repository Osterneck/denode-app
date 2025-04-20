from sqlalchemy import create_engine, inspect
import logging

logger = logging.getLogger(__name__)

def extract_schema(connection_url):
    """
    Extract the schema information from a database using SQLAlchemy inspection.
    
    Args:
        connection_url (str): SQLAlchemy connection URL
        
    Returns:
        dict: Dictionary with table names as keys and column/constraint information as values
    """
    try:
        engine = create_engine(connection_url)
        inspector = inspect(engine)
        schema = {}
        
        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            pk_constraint = inspector.get_pk_constraint(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)
            indexes = inspector.get_indexes(table_name)
            
            # Extract column information in a more readable format
            column_info = []
            for col in columns:
                column_info.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "default": str(col.get("default", "None")),
                    "is_primary_key": col.get("primary_key", False)
                })
            
            # Store comprehensive table information
            schema[table_name] = {
                "columns": column_info,
                "primary_key": pk_constraint,
                "foreign_keys": foreign_keys,
                "indexes": indexes,
                "column_count": len(columns)
            }
        
        logger.info(f"Successfully extracted schema with {len(schema)} tables")
        return schema
    
    except Exception as e:
        logger.error(f"Error extracting schema: {str(e)}")
        raise
