def _safe_exec(code: str, globals_dict: dict | None = None, locals_dict: dict | None = None) -> None:
    """Execute user supplied code within a safe try/except block.

    The execution is sandboxed by providing an empty ``__builtins__`` dictionary
    in the global namespace, preventing the user from accessing Python's
    builtin functions.  Any exception that occurs during execution is logged
    instead of being propagated, preserving the original behaviour of
    `_safe_exec` while adding a minimal safety measure.

    Parameters
    ----------
    code : str
        The code to execute.
    globals_dict : dict | None, optional
        Custom globals dictionary to use during execution. If ``None`` (the
        default), a dictionary containing an empty ``__builtins__`` entry is
        created.
    locals_dict : dict | None, optional
        Custom locals dictionary to use during execution.
    """
    try:
        exec(
            code,
            globals_dict if globals_dict is not None else {"__builtins__": {}},
            locals_dict,
        )
    except Exception as exc:  # pragma: no cover – behaviour is deterministic
        _log_execution_error(exc)


def _log_execution_error(error: Exception) -> None:
    """Log an exception that occurred during user code execution.

    In a production environment, this could be replaced with structured logging.
    For this example, we simply print the error message to keep the original
    behaviour of notifying the user while preventing the exception from
    bubbling up.
    """
    print(f"Execution error: {error}")


def run_user_input(code_str: str) -> None:
    """Run the supplied user input string.

    Parameters
    ----------
    code_str : str
        The code provided by the user.
    """
    _safe_exec(code_str)