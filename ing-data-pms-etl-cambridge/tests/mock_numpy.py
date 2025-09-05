class ndarray:
    pass

def array(*args, **kwargs):
    return []

def zeros(*args, **kwargs):
    return [0] * (args[0] if args else 1)

def ones(*args, **kwargs):
    return [1] * (args[0] if args else 1)

def arange(*args, **kwargs):
    return list(range(*args))

def mean(*args, **kwargs):
    return 0

def std(*args, **kwargs):
    return 0 