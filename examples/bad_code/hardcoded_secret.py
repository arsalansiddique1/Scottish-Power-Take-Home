import os


def _get_production_api_key() -> str:
    """Retrieve the production API key from an environment variable.
    
    The key is required for the application to function. If it is not
    present, a RuntimeError is raised so that the failure is obvious at
    start‑up time.
    """
    key = os.getenv("PRODUCTION_API_KEY")
    if not key:
        raise RuntimeError("Missing required environment variable 'PRODUCTION_API_KEY'")
    return key

# Expose the API key as a runtime variable. The name follows the
# project's snake_case convention instead of using ALL_CAPS.
production_api_key = _get_production_api_key()


def ping():
    return "ok"