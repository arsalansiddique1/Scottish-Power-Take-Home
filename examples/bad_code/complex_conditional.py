def should_process(a, b, c, d, e):
    """Determine whether the process should run.

    The original implementation combined several AND/OR clauses
    in a single return statement, which made it difficult to read and
    reason about. ``should_process`` now delegates the complex part to
    ``is_valid_combination`` which clearly describes the intent of the
    predicate.

    Parameters
    ----------
    a, b, c, d, e : bool
        Input flags.

    Returns
    -------
    bool
        ``True`` only when ``a`` is true and at least one of the
        following combinations is satisfied: ``b and c``, ``d and e`` or
        ``c and e``.
    """
    return a and is_valid_combination(b, c, d, e)


def is_valid_combination(b, c, d, e):
    return any((b and c, d and e, c and e))