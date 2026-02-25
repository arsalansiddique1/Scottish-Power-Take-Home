def needs_refactor(a, b, c, d):
    if (a and b and c) or (a and c and d) or (b and c and d):
        return 1
    return 0
