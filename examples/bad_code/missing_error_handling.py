def load_payload(file_path: str) -> str:
    """Load payload from the given file path with robust error handling.

    The function reads the entire contents of *file_path* and returns it as a
    string.  It uses a context manager to guarantee that the file handle is
    closed even for errors.  A user‑friendly ``RuntimeError`` is raised for
    any I/O issue, preserving the original exception as the context.
    """

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, PermissionError) as e:
        raise RuntimeError(f"Error reading file {file_path}: {e}") from e
    except OSError as e:
        raise RuntimeError(f"Error reading file {file_path}: {e}") from e