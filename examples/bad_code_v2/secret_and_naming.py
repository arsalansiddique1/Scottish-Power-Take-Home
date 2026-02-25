import os

# Retrieve the service token from an environment variable. If not present, use a default value.
# This allows you to keep the token out of the source code and makes rotation easier.
service_token = os.getenv("SERVICE_TOKEN", "dev_token_please_rotate")


def auth_header():
    """Return a dictionary for use in HTTP Authorization headers.

    The header contains a Bearer token derived from :data:`service_token`.
    ``auth_header`` keeps the public API unchanged while internally using a
    snake_case variable name.
    """
    return {"Authorization": f"Bearer {service_token}"}