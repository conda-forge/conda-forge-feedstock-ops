import logging
from collections.abc import Callable
from typing import (
    IO,
    Any,
)

import orjson

logger = logging.getLogger(__name__)


def default(obj: Any) -> Any:
    """For custom object serialization.

    Raises
    ------
    TypeError
        If the object is not JSON serializable.
    """
    if isinstance(obj, set):
        return {"__set__": True, "elements": sorted(obj)}
    raise TypeError(repr(obj) + " is not JSON serializable")


def object_hook(dct: dict) -> set | dict:
    """For custom object deserialization."""
    if "__set__" in dct:
        return set(dct["elements"])
    return dct


def dumps(
    obj: Any,
    default: Callable[[Any], Any] = default,
) -> str:
    """Return a JSON string from a Python object."""
    return orjson.dumps(
        obj,
        option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2,
        default=default,
    ).decode("utf-8")


def dump(
    obj: Any,
    fp: IO[str],
    default: Callable[[Any], Any] = default,
) -> None:
    fp.write(dumps(obj, default=default))


def _call_object_hook(
    data: Any,
    object_hook: Callable[[dict], Any],
) -> Any:
    """Recursively calls object_hook depth-first."""
    if isinstance(data, list):
        return [_call_object_hook(d, object_hook) for d in data]
    elif isinstance(data, dict):
        for k in data:
            data[k] = _call_object_hook(data[k], object_hook)
        return object_hook(data)
    else:
        return data


def loads(s: str, object_hook: Callable[[dict], Any] = object_hook) -> dict:
    """Load a string as JSON, with appropriate object hooks."""
    data = orjson.loads(s)
    if object_hook is not None:
        data = _call_object_hook(data, object_hook)
    return data


def load(
    fp: IO[str],
    object_hook: Callable[[dict], Any] = object_hook,
) -> dict:
    """Load a file object as JSON, with appropriate object hooks."""
    return loads(fp.read())
