"""
DEnode JSON Serialization Fix

Simply include this in your webapp/app.py file:

import json

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

# Then after creating your Flask app:
app.json_encoder = SafeJSONEncoder
"""

import json

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
