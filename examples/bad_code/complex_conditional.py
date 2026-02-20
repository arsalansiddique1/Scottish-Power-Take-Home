def should_process(a, b, c, d, e):
    if (a and b and c) or (d and e and a) or (a and c and e):
        return True
    return False
