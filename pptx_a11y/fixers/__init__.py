ALL_FIXERS = []


def register(fn):
    ALL_FIXERS.append(fn)
    return fn


def load_all():
    from importlib import import_module
    for name in ("alt_text", "slide_titles", "metadata"):
        import_module(f"{__name__}.{name}")
    return ALL_FIXERS
