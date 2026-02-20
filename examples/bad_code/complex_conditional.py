def _any_pair_meets(b, c, d, e):
    """Return True if at least one of the following pairs is True:
    - b and c
    - d and e
    - c and e
    """
    return (b and c) or (d and e) or (c and e)

def should_process(a, b, c, d, e):
    """Determine whether processing should occur based on the provided flags.

    The original implementation performed a single, complex logical
    expression.  This refactoring extracts the pair‑checking logic into
    a helper function for readability while preserving the exact behavior.
    """
    return a and _any_pair_meets(b, c, d, e)