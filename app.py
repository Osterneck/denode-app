import os
import sys
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
import logging

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.schema_extractor import extract_schema
from db.query_log_analyzer import parse_query_logs, analyze_query_patterns
from engine.heuristics import recommend_changes
from engine.plan_generator import generate_sql
from engine.benchmark import PerformanceBenchmark
from storage.metadata_store import MetadataStore

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("denode-webapp")

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "denode-dev-key")
metadata_store = MetadataStore(base_path="./metadata")

@app.route('/')
def index():
    """Home page"""
    # Get list of databases
    databases = metadata_store.list_databases()
    return render_template('index.html', databases=databases)

@app.route('/extract', methods=['GET', 'POST'])
def extract():
    """Schema extraction page"""
    result = None
    error = None
    
    if request.method == 'POST':
        try:
            # Get database connection URL
            db_url = request.form.get('db_url')
            db_name = request.form.get('db_name')
            
            if not db_url:
                error = "Database URL is required"
            elif not db_name:
                error = "Database name identifier is required"
            else:
                # Extract schema
                result = extract_schema(db_url)
                
                # Save to metadata store
                if metadata_store.save_schema(result, db_name):
                    flash(f"Schema extracted and saved successfully for '{db_name}'", "success")
                    # Set session variable for current database
                    session['current_db'] = db_name
                    # Redirect to the analyze page
                    return redirect(url_for('analyze', db_name=db_name))
        
        except Exception as e:
            logger.error(f"Error extracting schema: {str(e)}")
            error = f"Error extracting schema: {str(e)}"
    
    return render_template('extract.html', result=result, error=error)

@app.route('/analyze', methods=['GET', 'POST'])
def analyze():
    """Query analysis page"""
    result = None
    error = None
    db_name = request.args.get('db_name', session.get('current_db'))
    schema_loaded = False
    
    # Try to load schema
    schema = None
    if db_name:
        schema = metadata_store.load_latest_schema(db_name)
        if schema:
            schema_loaded = True
    
    if request.method == 'POST':
        try:
            use_sample = request.form.get('use_sample_log') == 'yes'
            db_name = request.form.get('db_name', db_name)
            
            if not db_name:
                error = "Database name identifier is required"
            elif use_sample:
                # Use the sample query log file we created
                log_path = './data/query_log_sample.sql'
                
                # Parse the query logs
                result = parse_query_logs(log_path)
                
                # Perform advanced analysis if schema is available
                if schema:
                    advanced_analysis = analyze_query_patterns(result, schema)
                    result['advanced_analysis'] = advanced_analysis
                
                # Save to metadata store
                if metadata_store.save_query_analysis(result, db_name):
                    flash(f"Query analysis completed with sample data for '{db_name}'", "success")
                    # Set session variable for current database
                    session['current_db'] = db_name
                    # Redirect to the recommendations page
                    return redirect(url_for('recommendations', db_name=db_name))
            else:
                # Check if log file was uploaded
                if 'log_file' not in request.files:
                    error = "No log file uploaded"
                else:
                    log_file = request.files['log_file']
                    
                    if not log_file.filename:
                        error = "No log file selected"
                    else:
                        # Save the uploaded file temporarily
                        log_path = f"/tmp/{log_file.filename}"
                        log_file.save(log_path)
                        
                        # Parse the query logs
                        result = parse_query_logs(log_path)
                        
                        # Perform advanced analysis if schema is available
                        if schema:
                            advanced_analysis = analyze_query_patterns(result, schema)
                            result['advanced_analysis'] = advanced_analysis
                        
                        # Save to metadata store
                        if metadata_store.save_query_analysis(result, db_name):
                            flash(f"Query analysis completed and saved successfully for '{db_name}'", "success")
                            # Set session variable for current database
                            session['current_db'] = db_name
                            # Redirect to the recommendations page
                            return redirect(url_for('recommendations', db_name=db_name))
                        
                        # Clean up temporary file
                        os.remove(log_path)
        
        except Exception as e:
            logger.error(f"Error analyzing queries: {str(e)}")
            error = f"Error analyzing queries: {str(e)}"
    
    return render_template('analyze.html', db_name=db_name, schema_loaded=schema_loaded, result=result, error=error)

@app.route('/recommendations', methods=['GET', 'POST'])
def recommendations():
    """Recommendations page"""
    db_name = request.args.get('db_name', session.get('current_db'))
    
    # Try to load schema and query analysis from the store
    schema = None
    query_analysis = None
    recommendations = None
    error = None
    
    if db_name:
        schema = metadata_store.load_latest_schema(db_name)
        query_analysis = metadata_store.load_latest_query_analysis(db_name)
        
        # Check if we already have recommendations
        recommendations = metadata_store.load_latest_recommendations(db_name)
    
    if request.method == 'POST':
        try:
            # Generate new recommendations
            if not schema:
                error = "No schema available. Please extract the schema first."
            elif not query_analysis:
                error = "No query analysis available. Please analyze query logs first."
            else:
                recommendations = recommend_changes(schema, query_analysis)
                
                # Save to metadata store
                if metadata_store.save_recommendations(recommendations, db_name):
                    flash(f"Generated {len(recommendations)} recommendations for '{db_name}'", "success")
        
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            error = f"Error generating recommendations: {str(e)}"
    
    return render_template('recommendations.html', db_name=db_name, 
                          recommendations=recommendations, error=error)

@app.route('/generate_sql/<db_name>/<table>/<action>')
def generate_sql_page(db_name, table, action):
    """Generate SQL implementation page"""
    try:
        # Load schema and recommendations
        schema = metadata_store.load_latest_schema(db_name)
        recommendations = metadata_store.load_latest_recommendations(db_name)
        
        if not schema:
            return jsonify({"error": "Schema not found"}), 404
        
        if not recommendations:
            return jsonify({"error": "Recommendations not found"}), 404
        
        # Find the specific recommendation
        recommendation = next((r for r in recommendations if r['table'] == table and r['action'] == action), None)
        
        if not recommendation:
            return jsonify({"error": "Recommendation not found"}), 404
        
        # Generate SQL plan
        sql_plan = generate_sql(recommendation, schema)
        
        return render_template('sql_plan.html', db_name=db_name, plan=sql_plan)
    
    except Exception as e:
        logger.error(f"Error generating SQL: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/schemas/<db_name>')
def api_get_schema(db_name):
    """API to get schema for a database"""
    try:
        schema = metadata_store.load_latest_schema(db_name)
        if not schema:
            return jsonify({"error": "Schema not found"}), 404
        
        return jsonify(schema)
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analysis/<db_name>')
def api_get_analysis(db_name):
    """API to get query analysis for a database"""
    try:
        analysis = metadata_store.load_latest_query_analysis(db_name)
        if not analysis:
            return jsonify({"error": "Analysis not found"}), 404
        
        return jsonify(analysis)
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/recommendations/<db_name>')
def api_get_recommendations(db_name):
    """API to get recommendations for a database"""
    try:
        recommendations = metadata_store.load_latest_recommendations(db_name)
        if not recommendations:
            return jsonify({"error": "Recommendations not found"}), 404
        
        return jsonify(recommendations)
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sql_plan', methods=['POST'])
def api_generate_sql():
    """API to generate SQL plan for a recommendation"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        db_name = data.get('db_name')
        table = data.get('table')
        action = data.get('action')
        
        if not all([db_name, table, action]):
            return jsonify({"error": "Missing required parameters"}), 400
        
        # Load schema and recommendations
        schema = metadata_store.load_latest_schema(db_name)
        recommendations = metadata_store.load_latest_recommendations(db_name)
        
        if not schema:
            return jsonify({"error": "Schema not found"}), 404
        
        if not recommendations:
            return jsonify({"error": "Recommendations not found"}), 404
        
        # Find the specific recommendation
        recommendation = next((r for r in recommendations if r['table'] == table and r['action'] == action), None)
        
        if not recommendation:
            return jsonify({"error": "Recommendation not found"}), 404
        
        # Generate SQL plan
        sql_plan = generate_sql(recommendation, schema)
        
        return jsonify(sql_plan)
    
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/benchmark', methods=['GET', 'POST'])
def benchmark():
    """Performance benchmarking page"""
    result = None
    error = None
    db_name = request.args.get('db_name', session.get('current_db'))
    mode = request.args.get('mode', 'quick')
    
    # Default values
    db_url = os.environ.get('DATABASE_URL', '')
    query = "SELECT 1"
    
    if request.method == 'POST':
        try:
            db_url = request.form.get('db_url')
            mode = request.args.get('mode', 'quick')
            
            if not db_url:
                error = "Database connection URL is required"
            else:
                # Create benchmark tool
                benchmarker = PerformanceBenchmark(db_url)
                
                if mode == 'quick':
                    # Single query benchmark
                    query = request.form.get('query', 'SELECT 1')
                    iterations = int(request.form.get('iterations', 5))
                    warmup = int(request.form.get('warmup', 1))
                    
                    result = benchmarker.time_query(query, iterations=iterations, warmup=warmup)
                
                elif mode == 'compare':
                    # Compare two queries
                    query1 = request.form.get('query1', 'SELECT 1')
                    query2 = request.form.get('query2', 'SELECT 1')
                    iterations = int(request.form.get('iterations', 3))
                    
                    # Get results for both queries
                    result1 = benchmarker.time_query(query1, iterations=iterations)
                    result2 = benchmarker.time_query(query2, iterations=iterations)
                    
                    # Calculate improvement
                    improvement = (result1["avg"] - result2["avg"]) / result1["avg"] * 100
                    
                    result = {
                        "before": result1,
                        "after": result2,
                        "percent_improvement": improvement,
                        "absolute_improvement_ms": result1["avg"] - result2["avg"]
                    }
                    
                    # Update query for displaying in the form
                    query = query1
                
                elif mode == 'throughput':
                    # Throughput test
                    query = request.form.get('query', 'SELECT 1')
                    duration = int(request.form.get('duration', 5))
                    clients = int(request.form.get('clients', 5))
                    
                    result = benchmarker.run_throughput_test(query, duration=duration, concurrent_clients=clients)
                
                flash(f"Benchmark completed successfully", "success")
        
        except Exception as e:
            logger.error(f"Error running benchmark: {str(e)}")
            error = f"Error running benchmark: {str(e)}"
    
    # Add menu item to navbar for benchmark
    return render_template('benchmark.html', db_name=db_name, db_url=db_url,
                          query=query, mode=mode, result=result, error=error)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
