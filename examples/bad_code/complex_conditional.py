def should_process(a, b, c, d, e):
    """Determine whether to process based on input flags.

    The original condition was overly nested. It has been simplified to
    a clearer form without changing behaviour:

    ``a and ((b and c) or (e and (c or d)))``
    """
    return a and ((b and c) or (e and (c or d)))