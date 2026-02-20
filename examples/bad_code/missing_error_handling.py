def load_payload(path: str) -> str:
    """Load payload from the given file path with robust error handling.

    The function reads the entire contents of *path* and returns it as a
    string.  It uses a context manager to guarantee that the file handle is
    closed even for errors.  A user‑friendly ``RuntimeError`` is raised for
    any I/O issue, preserving the original exception as the context.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError as e:
        # The file does not exist.
        raise RuntimeError(f"File not found: {path}") from e
    except PermissionError as e:
        # The file is inaccessible due to permissions.
        raise RuntimeError(f"Permission denied when reading file: {path}") from e
    except OSError as e:
        # Any other OS‑related error.
        raise RuntimeError(f"Error reading file {path}: {e}") from e