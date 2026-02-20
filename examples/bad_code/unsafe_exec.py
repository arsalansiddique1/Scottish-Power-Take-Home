def _safe_exec(code: str) -> None:
    """Execute user supplied code within a safe try/except block.

    The function logs any exception that occurs during execution so that it
    does not propagate to callers and potentially crash the application.
    This preserves the original behaviour of executing the user code while
    adding minimal, non‑functional safety handling.
    """
    try:
        exec(code)
    except Exception as exc:  # pragma: no cover – behaviour is deterministic
        # Log the exception instead of letting it bubble up.
        # In a real application you would use the logging module.
        print(f"Execution error: {exc}")


def run_user_input(code_str: str) -> None:
    """Run the supplied user input string.

    Parameters
    ----------
    code_str : str
        The code provided by the user.
    """
    _safe_exec(code_str)