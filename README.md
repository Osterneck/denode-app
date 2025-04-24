# DEnode Fix for Render.com Deployment

This repository contains fixes for the 500 Internal Server Error in the DEnode application when deployed to Render.com.

## Quick Fix Instructions

### Option 1: Minimal JSON Serialization Fix

1. Open your `webapp/app.py` file
2. Add this code at the top (after the existing imports):

```python
# Fix for JSON serialization issues
class SafeJSONEncoder(json.JSONEncoder):
    def default(self, o):
        try:
            if hasattr(o, '__dict__'):
                return o.__dict__
            elif str(type(o)) == "<class 'jinja2.runtime.Undefined'>":
                return None
            return super().default(o)
        except:
            return str(o)
```

3. After creating your Flask app, add this line:

```python
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "denode-dev-key")
# Add this line:
app.json_encoder = SafeJSONEncoder
```

### Option 2: Complete Error Handling

For more comprehensive error handling, copy both the `webapp/app_fix.py` contents and the `webapp/templates/error.html` file to your application.

## Files Included

- `webapp/app_fix.py` - Code to add to your app.py file
- `webapp/json_fix.py` - Minimal JSON serialization fix
- `webapp/templates/error.html` - Error template for user-friendly error pages

## Common Issues Fixed

- JSON serialization errors with Jinja2 Undefined objects
- Uncaught exceptions causing 500 errors instead of friendly error pages
- Better error logging for debugging deployment issues

## After Deployment

After applying these fixes, your DEnode application should properly handle JSON serialization and display user-friendly error pages.
