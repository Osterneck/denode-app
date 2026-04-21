"""
This file contains modifications that should be applied to your existing app.py file.
The important parts to add are:

1. Import the traceback module at the top
2. Add the SafeJSONEncoder class
3. Set app.json_encoder = SafeJSONEncoder after creating your Flask app
4. Add the error handling setup function and call it after creating your app
"""

# Add this import with your other imports
import traceback

# Add this class before creating your Flask app
class SafeJSONEncoder(json.JSONEncoder):
    """JSON encoder that safely handles various non-serializable types"""
    def default(self, o):
        try:
            if hasattr(o, '__dict__'):
                return o.__dict__
            elif str(type(o)) == "<class 'jinja2.runtime.Undefined'>":
                return None
            elif hasattr(o, '__iter__') and not isinstance(o, (str, bytes, list, dict)):
                return list(o)
            return super().default(o)
        except:
            return str(o)  # Convert anything else to string as fallback

# Add this function before your route definitions
def setup_error_handling(app):
    """Set up basic error handling for the Flask app"""
    
    @app.errorhandler(500)
    def handle_500_error(e):
        """Handle 500 internal server errors"""
        app.logger.error(f"500 error: {str(e)}\n{traceback.format_exc()}")
        return render_template('error.html',
                             error="Internal server error occurred. Please try again later.",
                             title="Server Error"), 500
    
    @app.errorhandler(404)
    def handle_404_error(e):
        """Handle 404 not found errors"""
        return render_template('error.html',
                             error="The requested page was not found.",
                             title="Page Not Found"), 404
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        """Handle all uncaught exceptions"""
        app.logger.error(f"Unhandled exception: {str(e)}\n{traceback.format_exc()}")
        return render_template('error.html',
                             error="An unexpected error occurred. Please try again later.",
                             title="Unexpected Error"), 500

# ---- After creating your Flask app, add these lines: ----
# app = Flask(__name__)
# app.secret_key = os.environ.get("SESSION_SECRET", "denode-dev-key")
# 
# # Apply the fixes
# app.json_encoder = SafeJSONEncoder
# setup_error_handling(app)
