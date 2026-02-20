def has_pair_true(flag_b, flag_c, flag_d, flag_e):
    """Return True if any of the following flag pairs are simultaneously True:

    - flag_b and flag_c
    - flag_d and flag_e
    - flag_c and flag_e
    """
    return any([flag_b and flag_c, flag_d and flag_e, flag_c and flag_e])


def should_process(flag_a, flag_b, flag_c, flag_d, flag_e):
    """Determine whether processing should occur based on the provided flags.

    The heavy logical expression has been compacted into a helper function
    for clarity while preserving the original behavior.
    """
    return flag_a and has_pair_true(flag_b, flag_c, flag_d, flag_e)