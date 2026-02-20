import os

# Retrieve the production API key from an environment variable, falling back to the original hardcoded value for backward compatibility.
production_api_key = os.getenv("PRODUCTION_API_KEY", "hardcoded_prod_key_123")
# Keep the original name as an alias to preserve compatibility with any existing imports.
PRODUCTION_API_KEY = production_api_key


def ping():
    return "ok"