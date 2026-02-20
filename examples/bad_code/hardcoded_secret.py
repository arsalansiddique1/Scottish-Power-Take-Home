import os


def _load_production_api_key() -> str:
    """Read the production API key from the environment, falling back to a hardcoded default.
    This helper centralises the logic for loading the key and keeps the default value for
    backward‑compatibility while encouraging the use of an environment variable.
    """
    return os.getenv("PRODUCTION_API_KEY", "hardcoded_prod_key_123")

# Use snake_case for the module‑level variable, improving consistency with the code style.
production_api_key = _load_production_api_key()


def ping() -> str:
    """Return a simple pong response."""
    return "ok"