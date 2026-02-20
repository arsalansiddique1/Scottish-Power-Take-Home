def _safe_exec(code: str) -> None:
    """Execute user supplied code in a sandboxed environment.
    Only the code is executed; builtins are removed to prevent access to
    dangerous modules or functions. Commonly, developers extend this
    pattern with a more sophisticated set of allowed globals.
    """
    # Provide a limited set of globals; here we deliberately remove all
    # builtins to avoid accidental access to filesystem or other
    # privileged APIs.
    safe_globals: dict = {"__builtins__": {}}
    try:
        exec(code, safe_globals)
    except Exception as exc:  # pragma: no cover  (execution errors are user‑generated)
        # Reraise as a RuntimeError to keep the caller’s exception context
        # but provide a clearer message.
        raise RuntimeError("User code execution failed") from exc


def run_user_input(code: str) -> None:
    """Entry point for executing user supplied code.

    Parameters
    ----------
    code: str
        Raw Python code supplied by the user.

    Notes
    -----
    The function delegates to :func:`_safe_exec` which runs the code in a
    sandboxed context. The explicit naming of the parameter improves
    readability and aligns with the conceptual model of *code*,
    distinct from *user_input*.
    """
    _safe_exec(code)