def read_config(file_path: str) -> str:
    """Read and return the contents of a configuration file.

    This function now ensures the file is opened in a context manager and
    includes a generic exception handler that re‑raises a more informative
    I/O error while preserving the original exception context.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as exc:
        raise IOError(f"Failed to read config at {file_path}") from exc