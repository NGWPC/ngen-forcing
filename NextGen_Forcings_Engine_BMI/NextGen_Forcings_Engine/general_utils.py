"""General utilities"""

import json
import logging
import typing

import numpy as np

JSON_NOT_SERIALIZABLE_FORMAT = "ERR_NOT_JSON_SERIALIZABLE:TYPE:{typ}"


class ExpectVsActualError(Exception):
    """Raised by assert_equal_with_tol"""


def serializer_with_fallback(obj: typing.Any):
    """Serializer for json.dump to handle typical types, numpy types, and non-serializable types,
    which are converted to a string composed of a sentinel and the type as the suffix.
    To be used as the `default=` parameter when calling json dump/dumps.
    Not to be called directly.
    """
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        return obj.item()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    # It is not serializable
    return JSON_NOT_SERIALIZABLE_FORMAT.format(typ=str(type(obj)))


def serialize_to_json(
    obj: typing.Any,
    out_file: str = None,
    sort_keys: bool = False,
    keep_keys: tuple = None,
) -> str:
    """Serialize the provided object.
    Parameters:
        out_file: optionally write it to a new file.
        sort_keys: optionally sort the keys (passed to json.dumps kwarg sort_keys).
        keep_keys: optionally filter it to keep only the keep_keys.
    Returns:
        A JSON string representation of the object.
    """
    dump_kwargs = {
        "default": serializer_with_fallback,
        "indent": 2,
        "sort_keys": sort_keys,
    }
    json_str = json.dumps(obj, **dump_kwargs)

    # Optionally filter
    if keep_keys:
        tmp = json.loads(json_str)
        tmp = {k: v for k, v in tmp.items() if k in keep_keys}
        json_str = json.dumps(tmp, **dump_kwargs)
        del tmp

    # Optionally write to file
    if out_file is not None:
        logging.info(f"Writing: {out_file}")
        with open(out_file, "w") as f:
            f.write(json_str)

    return json_str


def assert_equal_with_tol(
    expect: dict,
    actual: dict,
    keys_to_check: tuple | None = None,
    absolute_tolerance: float = 1e-6,
    relative_tolerance: float = 1e-10,
):
    """Assert that the key,value pairs in `expect` have matching key,value pairs in `actual`, with numerical tolerance.
    It is okay if actual has extra keys that are not present in expect.
    If keys_to_check is defined, then only those keys will be checked.
    Raises ExpectVsActualError.
    """
    errors: list[Exception] = []
    logging.info(
        f"Asserting equality with absolute tolerance {absolute_tolerance} and relative tolerance {relative_tolerance} for {len(expect)} keys: {list(expect.keys())}"
    )
    if keys_to_check:
        keys_missing = set(keys_to_check) - set(actual)
        if keys_missing:
            errors.append(KeyError(f"Missing keys: {keys_missing}"))

    for k, v_expect in expect.items():
        if keys_to_check and k not in keys_to_check:
            continue
        logging.debug(f"Key {repr(k)} has expected value {v_expect}")

        ### Check key existence
        try:
            v_actual = actual[k]
        except KeyError:
            msg = f"Key {k} in expected data is missing from actual"
            errors.append(KeyError(msg))
            continue
        logging.debug(
            f"Key {repr(k)} has expected value {v_expect} and actual value {v_actual}"
        )

        ### Check type match
        if type(v_actual) is not type(v_expect):
            errors.append(
                TypeError(
                    f"Type mismatch: type(v_actual) is not type(v_expect): {type(v_actual)} vs {type(v_expect)}"
                )
            )
            continue

        ### Check equality
        if v_expect == v_actual:
            continue
        ### This also works for strings and string arrays
        if np.array_equal(np.atleast_1d(v_expect), np.atleast_1d(v_actual)):
            continue
        ### Apply numerical tolerance
        try:
            if np.allclose(
                np.atleast_1d(v_expect),
                np.atleast_1d(v_actual),
                atol=absolute_tolerance,
                rtol=relative_tolerance,
            ):
                continue
        except np.exceptions.DTypePromotionError:
            errors.append(
                ValueError(
                    f"Expected not equal to actual, and could not apply np.allclose. expect={expect}, actual={actual}."
                )
            )
            continue

        errors.append(
            ValueError(
                f"Objects not equal, and numerical tolerances (atol={absolute_tolerance} rtol={relative_tolerance}) exceeded for at least one element. {v_expect} vs {v_actual}."
            )
        )

    if errors:
        raise ExpectVsActualError(errors)
