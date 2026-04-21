import click
import logging
import os
import sys
import json
from tabulate import tabulate

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.schema_extractor import extract_schema
from db.query_log_analyzer import parse_query_logs, analyze_query_patterns
from engine.simulator import run_explain, simulate_performance
from engine.heuristics import recommend_changes
from engine.plan_generator import generate_sql
from storage.metadata_store import MetadataStore

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("denode-cli")

@click.group()
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, verbose):
    """DEnode - Database Schema Optimization Tool"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize context
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['metadata_store'] = MetadataStore()

@cli.command()
@click.option('--db-url', required=True, help='Database connection URL')
@click.option('--output', '-o', help='Output file for schema (JSON)')
@click.option('--db-name', help='Name identifier for the database', default='default')
@click.pass_context
def extract(ctx, db_url, output, db_name):
    """Extract database schema information"""
    try:
        logger.info(f"Extracting schema from {db_url}")
        schema = extract_schema(db_url)
        
        if schema:
            # Print summary
            print(f"\nSchema extracted successfully: {len(schema)} tables found\n")
            
            # Print table summary
            table_rows = []
            for table_name, table_info in schema.items():
                columns = len(table_info['columns'])
                pk = 'Yes' if table_info['primary_key'].get('constrained_columns') else 'No'
                fks = len(table_info.get('foreign_keys', []))
                indexes = len(table_info.get('indexes', []))
                table_rows.append([table_name, columns, pk, fks, indexes])
            
            print(tabulate(table_rows, 
                         headers=['Table', 'Columns', 'Has PK', 'Foreign Keys', 'Indexes'],
                         tablefmt='grid'))
            
            # Save schema if output file is specified
            if output:
                with open(output, 'w') as f:
                    json.dump(schema, f, indent=2)
                print(f"\nSchema saved to {output}")
            
            # Save to metadata store
            if ctx.obj['metadata_store'].save_schema(schema, db_name):
                print(f"\nSchema saved to metadata store with ID '{db_name}'")
            
            return schema
        else:
            logger.error("No schema information was extracted")
    
    except Exception as e:
        logger.error(f"Error extracting schema: {str(e)}")
        raise click.ClickException(f"Schema extraction failed: {str(e)}")

@cli.command()
@click.option('--log-file', required=True, help='SQL query log file')
@click.option('--schema-file', help='Schema file (JSON) for advanced analysis')
@click.option('--output', '-o', help='Output file for analysis (JSON)')
@click.option('--db-name', help='Name identifier for the database', default='default')
@click.pass_context
def analyze(ctx, log_file, schema_file, output, db_name):
    """Analyze SQL query patterns from logs"""
    try:
        logger.info(f"Analyzing query logs from {log_file}")
        
        # Parse query logs
        query_data = parse_query_logs(log_file)
        
        # Load schema if provided
        schema = None
        if schema_file:
            with open(schema_file, 'r') as f:
                schema = json.load(f)
        else:
            # Try to load from metadata store
            schema = ctx.obj['metadata_store'].load_latest_schema(db_name)
        
        # Perform advanced analysis if schema is available
        if schema:
            print("\nPerforming advanced analysis with schema information...\n")
            advanced_analysis = analyze_query_patterns(query_data, schema)
            query_data['advanced_analysis'] = advanced_analysis
        
        # Print analysis summary
        print("\nQuery Analysis Summary:")
        print(f"Total Queries: {query_data['query_counts']['total']}")
        print(f"SELECT Queries: {query_data['query_counts']['select']}")
        print(f"INSERT Queries: {query_data['query_counts']['insert']}")
        print(f"UPDATE Queries: {query_data['query_counts']['update']}")
        print(f"DELETE Queries: {query_data['query_counts']['delete']}")
        print(f"\nJoin Analysis:")
        print(f"Total Joins: {query_data['join_analysis']['total_joins']}")
        print(f"Inner Joins: {query_data['join_analysis']['inner_joins']}")
        print(f"Left Joins: {query_data['join_analysis']['left_joins']}")
        print(f"Right Joins: {query_data['join_analysis']['right_joins']}")
        print(f"\nRead/Write Ratio: {query_data['read_write_ratio']:.2f}")
        
        # Print table access frequency
        if query_data['table_access']:
            print("\nTable Access Frequency:")
            table_rows = []
            for table, count in sorted(query_data['table_access'].items(), 
                                      key=lambda x: x[1], reverse=True):
                table_rows.append([table, count, 
                                  f"{count/query_data['query_counts']['total']*100:.1f}%"])
            
            print(tabulate(table_rows, 
                         headers=['Table', 'Access Count', 'Percentage'],
                         tablefmt='grid'))
        
        # Save analysis if output file is specified
        if output:
            with open(output, 'w') as f:
                json.dump(query_data, f, indent=2)
            print(f"\nAnalysis saved to {output}")
        
        # Save to metadata store
        if ctx.obj['metadata_store'].save_query_analysis(query_data, db_name):
            print(f"\nQuery analysis saved to metadata store with ID '{db_name}'")
        
        return query_data
        
    except Exception as e:
        logger.error(f"Error analyzing query logs: {str(e)}")
        raise click.ClickException(f"Query analysis failed: {str(e)}")

@cli.command()
@click.option('--db-url', help='Database connection URL')
@click.option('--query', help='SQL query to explain')
@click.option('--query-file', help='File containing SQL query')
@click.option('--analyze', is_flag=True, default=True, help='Execute query for actual statistics')
@click.pass_context
def explain(ctx, db_url, query, query_file, analyze):
    """Run EXPLAIN on a SQL query"""
    try:
        if not query and not query_file:
            raise click.ClickException("Either --query or --query-file must be specified")
        
        if not db_url:
            raise click.ClickException("Database URL is required")
        
        if query_file:
            with open(query_file, 'r') as f:
                query = f.read()
        
        logger.info(f"Running EXPLAIN on query")
        explain_result = run_explain(db_url, query, analyze=analyze)
        
        print("\nQuery Execution Plan:")
        
        if 'error' in explain_result:
            print(f"Error: {explain_result['error']}")
        else:
            # Print the metrics
            if explain_result.get('metrics'):
                print("\nPerformance Metrics:")
                for metric, value in explain_result['metrics'].items():
                    print(f"{metric.replace('_', ' ').title()}: {value}")
            
            # Print the raw output
            print("\nDetailed Execution Plan:")
            for row in explain_result['raw_output']:
                print(row)
        
        return explain_result
        
    except Exception as e:
        logger.error(f"Error running EXPLAIN: {str(e)}")
        raise click.ClickException(f"EXPLAIN failed: {str(e)}")

@cli.command()
@click.option('--schema-file', help='Schema file (JSON)')
@click.option('--analysis-file', help='Query analysis file (JSON)')
@click.option('--db-name', help='Name identifier for the database to load data from store', default='default')
@click.option('--output', '-o', help='Output file for recommendations (JSON)')
@click.pass_context
def recommend(ctx, schema_file, analysis_file, db_name, output):
    """Generate optimization recommendations"""
    try:
        schema = None
        query_analysis = None
        
        # Load schema
        if schema_file:
            with open(schema_file, 'r') as f:
                schema = json.load(f)
        else:
            # Try to load from metadata store
            schema = ctx.obj['metadata_store'].load_latest_schema(db_name)
            if not schema:
                raise click.ClickException("No schema found. Please provide a schema file or ensure it exists in the store.")
        
        # Load query analysis
        if analysis_file:
            with open(analysis_file, 'r') as f:
                query_analysis = json.load(f)
        else:
            # Try to load from metadata store
            query_analysis = ctx.obj['metadata_store'].load_latest_query_analysis(db_name)
            if not query_analysis:
                raise click.ClickException("No query analysis found. Please provide an analysis file or ensure it exists in the store.")
        
        logger.info("Generating optimization recommendations")
        recommendations = recommend_changes(schema, query_analysis)
        
        # Print recommendations
        print("\nOptimization Recommendations:\n")
        
        if not recommendations:
            print("No optimization recommendations identified.")
        else:
            for i, rec in enumerate(recommendations, 1):
                print(f"{i}. {rec['action']} table '{rec['table']}' - {rec['confidence']}% confidence")
                print(f"   Reason: {rec['reason']}")
                print()
        
        # Save recommendations if output file is specified
        if output:
            with open(output, 'w') as f:
                json.dump(recommendations, f, indent=2)
            print(f"\nRecommendations saved to {output}")
        
        # Save to metadata store
        if ctx.obj['metadata_store'].save_recommendations(recommendations, db_name):
            print(f"\nRecommendations saved to metadata store with ID '{db_name}'")
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        raise click.ClickException(f"Recommendation generation failed: {str(e)}")

@cli.command()
@click.option('--schema-file', help='Schema file (JSON)')
@click.option('--rec-file', help='Recommendations file (JSON)')
@click.option('--db-name', help='Name identifier for the database to load data from store', default='default')
@click.option('--table', help='Specific table to generate SQL for')
@click.option('--action', help='Specific action to generate SQL for', 
             type=click.Choice(['DENORMALIZE', 'NORMALIZE', 'INDEX', 'PARTITION'], case_sensitive=False))
@click.option('--output-dir', help='Directory to save SQL files')
@click.pass_context
def generate(ctx, schema_file, rec_file, db_name, table, action, output_dir):
    """Generate SQL implementation plan for recommendations"""
    try:
        schema = None
        recommendations = None
        
        # Load schema
        if schema_file:
            with open(schema_file, 'r') as f:
                schema = json.load(f)
        else:
            # Try to load from metadata store
            schema = ctx.obj['metadata_store'].load_latest_schema(db_name)
            if not schema:
                raise click.ClickException("No schema found. Please provide a schema file or ensure it exists in the store.")
        
        # Load recommendations
        if rec_file:
            with open(rec_file, 'r') as f:
                recommendations = json.load(f)
        else:
            # Try to load from metadata store
            recommendations = ctx.obj['metadata_store'].load_latest_recommendations(db_name)
            if not recommendations:
                raise click.ClickException("No recommendations found. Please provide a recommendations file or ensure it exists in the store.")
        
        # Filter recommendations if table or action is specified
        filtered_recs = recommendations
        if table:
            filtered_recs = [r for r in filtered_recs if r['table'] == table]
        
        if action:
            filtered_recs = [r for r in filtered_recs if r['action'] == action.upper()]
        
        if not filtered_recs:
            print("No matching recommendations found.")
            return []
        
        # Generate SQL for each recommendation
        sql_plans = []
        for rec in filtered_recs:
            logger.info(f"Generating SQL plan for {rec['action']} on {rec['table']}")
            plan = generate_sql(rec, schema)
            sql_plans.append(plan)
            
            # Print the plan
            print(f"\n{'='*80}")
            print(f"SQL PLAN: {plan['action']} for table '{plan['table']}'")
            print(f"{'='*80}")
            
            if 'error' in plan:
                print(f"Error: {plan['error']}")
                continue
            
            print(f"\nExplanation: {plan['explanation']}")
            
            if plan['caution']:
                print(f"\nCaution: {plan['caution']}")
            
            print("\nSQL Statements:")
            for i, stmt in enumerate(plan['statements'], 1):
                print(f"\n-- Statement {i}: {stmt['type']}")
                print(stmt['sql'])
            
            # Save SQL to file if output directory is specified
            if output_dir:
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                
                file_name = f"{plan['table']}_{plan['action'].lower()}.sql"
                file_path = os.path.join(output_dir, file_name)
                
                with open(file_path, 'w') as f:
                    f.write(f"-- SQL Plan: {plan['action']} for table '{plan['table']}'\n")
                    f.write(f"-- Generated on: {os.path.basename(__file__)}\n\n")
                    
                    f.write(f"-- Explanation: {plan['explanation']}\n")
                    
                    if plan['caution']:
                        f.write(f"-- Caution: {plan['caution']}\n")
                    
                    f.write("\n-- SQL Statements:\n")
                    for i, stmt in enumerate(plan['statements'], 1):
                        f.write(f"\n-- Statement {i}: {stmt['type']}\n")
                        f.write(f"{stmt['sql']}\n")
                
                print(f"\nSQL saved to {file_path}")
        
        return sql_plans
        
    except Exception as e:
        logger.error(f"Error generating SQL: {str(e)}")
        raise click.ClickException(f"SQL generation failed: {str(e)}")

@cli.command()
@click.option('--db-url', required=True, help='Database connection URL')
@click.option('--log-file', required=True, help='SQL query log file')
@click.option('--db-name', help='Name identifier for the database', default='default')
@click.option('--output-dir', help='Directory to save output files')
@click.pass_context
def full_analyze(ctx, db_url, log_file, db_name, output_dir):
    """Run full analysis pipeline: extract, analyze, recommend, generate"""
    try:
        # Create output directory if specified
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Step 1: Extract schema
        print("\n=== Step 1: Extracting Database Schema ===\n")
        schema = ctx.invoke(extract, db_url=db_url, 
                          output=os.path.join(output_dir, "schema.json") if output_dir else None,
                          db_name=db_name)
        
        # Step 2: Analyze query logs
        print("\n=== Step 2: Analyzing Query Patterns ===\n")
        query_analysis = ctx.invoke(analyze, log_file=log_file, 
                                  output=os.path.join(output_dir, "analysis.json") if output_dir else None,
                                  db_name=db_name)
        
        # Step 3: Generate recommendations
        print("\n=== Step 3: Generating Optimization Recommendations ===\n")
        recommendations = ctx.invoke(recommend, 
                                   output=os.path.join(output_dir, "recommendations.json") if output_dir else None,
                                   db_name=db_name)
        
        if not recommendations:
            print("\nNo recommendations generated. Stopping pipeline.")
            return
        
        # Step 4: Generate SQL
        print("\n=== Step 4: Generating SQL Implementation Plans ===\n")
        sql_plans = ctx.invoke(generate, 
                             output_dir=os.path.join(output_dir, "sql") if output_dir else None,
                             db_name=db_name)
        
        print(f"\n=== Analysis Pipeline Complete for '{db_name}' ===")
        print(f"Found {len(schema)} tables")
        print(f"Analyzed {query_analysis['query_counts']['total']} queries")
        print(f"Generated {len(recommendations)} recommendations")
        print(f"Created {len(sql_plans)} SQL implementation plans")
        
        return {
            "schema": schema,
            "query_analysis": query_analysis,
            "recommendations": recommendations,
            "sql_plans": sql_plans
        }
        
    except Exception as e:
        logger.error(f"Error in full analysis pipeline: {str(e)}")
        raise click.ClickException(f"Analysis pipeline failed: {str(e)}")

if __name__ == '__main__':
    cli(obj={})
