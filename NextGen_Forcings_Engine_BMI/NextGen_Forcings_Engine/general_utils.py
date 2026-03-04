"""General utilities"""

import json
import logging

import numpy as np

JSON_NOT_SERIALIZABLE_FORMAT = "ERR_NOT_JSON_SERIALIZABLE:TYPE:{typ}"


class ExpectVsActualError(Exception):
    """Raised by assert_equal_with_tol"""


def serializer_with_fallback(obj):
    """Serializer for json.dump to handle typical types, numpy types, and non-serializable types,
    which are converted to a string composed of a sentinel and the type as the suffix.
    """
    if hasattr(obj, "__dict__"):
        # It is serializable
        return obj.__dict__
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.generic):
        return obj.item()
    else:
        # It is not serializable
        return JSON_NOT_SERIALIZABLE_FORMAT.format(typ=str(type(obj)))


def serialize_to_json(
    obj,
    out_file: str = None,
    sort_keys: bool = False,
    keep_keys: tuple = None,
) -> str:
    """Serialize the provided object.
    Optionally sort it alphabetically.
    Optionally filter it to keep only the keep_keys.
    Optionally write it to a new file.
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
):
    """Assert that the key,value pairs in `expect` have matching key,value pairs in `actual`, with numerical tolerance.
    It is okay if actual has extra keys that are not present in expect.
    If keys_to_check is defined, then only those keys will be checked.
    """
    numerical_tolerance = 1e-6
    errors: list[Exception] = []
    logging.info(
        f"Asserting equality with numerical tolerance {numerical_tolerance} for {len(expect)} keys: {list(expect.keys())}"
    )
    keys_missing = set(keys_to_check) - set(actual)
    if keys_missing:
        errors.append(KeyError(f"Missing keys: {keys_missing}"))

    for k, v_expect in expect.items():
        if keys_to_check and k not in keys_to_check:
            continue
        logging.debug(f"Key {repr(k)} has expected value {v_expect}")
        try:
            v_actual = actual[k]
        except KeyError:
            errors.append(KeyError(f"Key {k} in expected data is missing from actual"))
        logging.debug(
            f"Key {repr(k)} has expected value {v_expect} and actual value {v_actual}"
        )
        if isinstance(v_expect, (float, int)):
            if abs(v_expect - v_actual) > numerical_tolerance:
                errors.append(
                    ValueError(
                        f"numerical tolerance {numerical_tolerance} exceeded by abs(v_expect - v_actual): abs({v_expect} - {v_actual}) == {abs(v_expect - v_actual)}"
                    )
                )
        elif v_actual != v_expect:
            errors.append(
                ValueError(
                    f"Not equal: for key {repr(k)},\nexpected:\n{v_expect}\n\nbut got:\n{v_actual}"
                )
            )
    if errors:
        raise ExpectVsActualError(errors)
