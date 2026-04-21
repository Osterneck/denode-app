import json
import os
import logging
from datetime import datetime
import sqlite3

logger = logging.getLogger(__name__)

class MetadataStore:
    """
    Storage manager for database schema and analysis metadata.
    Provides both JSON file and SQLite database storage options.
    """
    
    def __init__(self, base_path="./metadata", use_sqlite=True):
        """
        Initialize the metadata store.
        
        Args:
            base_path (str): Base directory to store metadata
            use_sqlite (bool): Whether to use SQLite for storage
        """
        self.base_path = base_path
        self.use_sqlite = use_sqlite
        
        # Create base directory if it doesn't exist
        if not os.path.exists(base_path):
            os.makedirs(base_path)
        
        if use_sqlite:
            self._init_sqlite_db()
    
    def _init_sqlite_db(self):
        """Initialize SQLite database schema"""
        db_path = os.path.join(self.base_path, "metadata.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS schema_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            db_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            schema_snapshot_data TEXT NOT NULL
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS query_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            db_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            analysis_data TEXT NOT NULL
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            db_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            recommendations TEXT NOT NULL
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_schema(self, schema, db_name="default"):
        """
        Save database schema information.
        
        Args:
            schema (dict): Schema information from schema_extractor
            db_name (str): Identifier for the database
            
        Returns:
            bool: Success flag
        """
        timestamp = datetime.now().isoformat()
        
        try:
            if self.use_sqlite:
                return self._save_to_sqlite("schema_snapshots", db_name, timestamp, schema)
            else:
                return self._save_to_json(schema, db_name, "schema", timestamp)
        except Exception as e:
            logger.error(f"Error saving schema: {str(e)}")
            return False
    
    def save_query_analysis(self, analysis, db_name="default"):
        """
        Save query analysis results.
        
        Args:
            analysis (dict): Query analysis from query_log_analyzer
            db_name (str): Identifier for the database
            
        Returns:
            bool: Success flag
        """
        timestamp = datetime.now().isoformat()
        
        try:
            if self.use_sqlite:
                return self._save_to_sqlite("query_analysis", db_name, timestamp, analysis)
            else:
                return self._save_to_json(analysis, db_name, "query_analysis", timestamp)
        except Exception as e:
            logger.error(f"Error saving query analysis: {str(e)}")
            return False
    
    def save_recommendations(self, recommendations, db_name="default"):
        """
        Save optimization recommendations.
        
        Args:
            recommendations (list): Recommendations from recommend_changes
            db_name (str): Identifier for the database
            
        Returns:
            bool: Success flag
        """
        timestamp = datetime.now().isoformat()
        
        try:
            if self.use_sqlite:
                return self._save_to_sqlite("recommendations", db_name, timestamp, recommendations)
            else:
                return self._save_to_json(recommendations, db_name, "recommendations", timestamp)
        except Exception as e:
            logger.error(f"Error saving recommendations: {str(e)}")
            return False
    
    def _save_to_json(self, data, db_name, data_type, timestamp):
        """
        Save data to a JSON file.
        
        Args:
            data: Data to save
            db_name (str): Database identifier
            data_type (str): Type of data being saved
            timestamp (str): Timestamp for the data
            
        Returns:
            bool: Success flag
        """
        # Create db directory if it doesn't exist
        db_dir = os.path.join(self.base_path, db_name)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        # Create a filename with timestamp
        filename = f"{data_type}_{timestamp.replace(':', '-')}.json"
        file_path = os.path.join(db_dir, filename)
        
        # Save with pretty formatting
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved {data_type} to {file_path}")
        return True
    
    def _save_to_sqlite(self, table, db_name, timestamp, data):
        """
        Save data to SQLite database.
        
        Args:
            table (str): Table name to save to
            db_name (str): Database identifier
            timestamp (str): Timestamp for the data
            data: Data to save
            
        Returns:
            bool: Success flag
        """
        db_path = os.path.join(self.base_path, "metadata.db")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # JSON serialize the data
        json_data = json.dumps(data)
        
        # Insert into the appropriate table
        cursor.execute(f'''
        INSERT INTO {table} (db_name, timestamp, {table.rstrip('s')}_data)
        VALUES (?, ?, ?)
        ''', (db_name, timestamp, json_data))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Saved {table} data to SQLite for {db_name}")
        return True
    
    def load_latest_schema(self, db_name="default"):
        """
        Load the latest schema for a database.
        
        Args:
            db_name (str): Database identifier
            
        Returns:
            dict: Schema information or None if not found
        """
        try:
            if self.use_sqlite:
                return self._load_latest_from_sqlite("schema_snapshots", db_name)
            else:
                return self._load_latest_from_json(db_name, "schema")
        except Exception as e:
            logger.error(f"Error loading schema: {str(e)}")
            return None
    
    def load_latest_query_analysis(self, db_name="default"):
        """
        Load the latest query analysis for a database.
        
        Args:
            db_name (str): Database identifier
            
        Returns:
            dict: Query analysis or None if not found
        """
        try:
            if self.use_sqlite:
                return self._load_latest_from_sqlite("query_analysis", db_name)
            else:
                return self._load_latest_from_json(db_name, "query_analysis")
        except Exception as e:
            logger.error(f"Error loading query analysis: {str(e)}")
            return None
    
    def load_latest_recommendations(self, db_name="default"):
        """
        Load the latest recommendations for a database.
        
        Args:
            db_name (str): Database identifier
            
        Returns:
            list: Recommendations or None if not found
        """
        try:
            if self.use_sqlite:
                return self._load_latest_from_sqlite("recommendations", db_name)
            else:
                return self._load_latest_from_json(db_name, "recommendations")
        except Exception as e:
            logger.error(f"Error loading recommendations: {str(e)}")
            return None
    
    def _load_latest_from_json(self, db_name, data_type):
        """
        Load the latest data from JSON files.
        
        Args:
            db_name (str): Database identifier
            data_type (str): Type of data to load
            
        Returns:
            Data from the latest file or None if not found
        """
        db_dir = os.path.join(self.base_path, db_name)
        if not os.path.exists(db_dir):
            return None
        
        # Find all files of the given type
        files = [f for f in os.listdir(db_dir) if f.startswith(f"{data_type}_") and f.endswith(".json")]
        
        if not files:
            return None
        
        # Sort by timestamp (part of filename)
        files.sort(reverse=True)
        latest_file = os.path.join(db_dir, files[0])
        
        with open(latest_file, 'r') as f:
            data = json.load(f)
        
        logger.info(f"Loaded {data_type} from {latest_file}")
        return data
    
    def _load_latest_from_sqlite(self, table, db_name):
        """
        Load the latest data from SQLite.
        
        Args:
            table (str): Table name to load from
            db_name (str): Database identifier
            
        Returns:
            Data from the latest record or None if not found
        """
        db_path = os.path.join(self.base_path, "metadata.db")
        
        if not os.path.exists(db_path):
            return None
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        data_column = f"{table.rstrip('s')}_data"
        
        # Get the latest record
        cursor.execute(f'''
        SELECT {data_column} FROM {table}
        WHERE db_name = ?
        ORDER BY timestamp DESC
        LIMIT 1
        ''', (db_name,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            data = json.loads(row[0])
            logger.info(f"Loaded {table} data from SQLite for {db_name}")
            return data
        
        return None
    
    def list_databases(self):
        """
        List all databases with stored metadata.
        
        Returns:
            list: List of database names
        """
        if self.use_sqlite:
            db_path = os.path.join(self.base_path, "metadata.db")
            
            if not os.path.exists(db_path):
                return []
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT DISTINCT db_name FROM schema_snapshots
            ''')
            
            db_names = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            return db_names
        else:
            # List directories in the base path
            if not os.path.exists(self.base_path):
                return []
                
            return [d for d in os.listdir(self.base_path) 
                   if os.path.isdir(os.path.join(self.base_path, d))]
