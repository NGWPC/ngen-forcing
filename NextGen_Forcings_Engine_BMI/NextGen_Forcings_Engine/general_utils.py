"""General utilities."""

import functools


def setter_hardener(func):
    """Decorator for setters. Causes the setter to be hardened such that it
    asserts that the new value is either replacing None, or that the new value
    is equal to the existing value."""

    @functools.wraps(func)
    def wrapper(self, new_value):
        # Private attr attr_public is typical pattern, with underscore prepending the public attr attr_public.
        attr_public = func.__name__
        attr_private = f"_{attr_public}"
        # Current value, or None if not yet set.
        val_existing = getattr(self, attr_private, None)

        if val_existing is None or val_existing == new_value:
            return func(self, new_value)
        else:
            raise ValueError(
                f"Public attr {attr_public} (private attr {attr_private}) is hardened. It had already been set to non-None value {repr(val_existing)}, and proposed new value is {repr(new_value)}, which is not equal to the existing value."
            )

    return wrapper
