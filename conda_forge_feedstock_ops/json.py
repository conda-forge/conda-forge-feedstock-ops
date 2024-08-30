import logging
from collections.abc import Callable
from typing import (
    IO,
    Any,
    Set,
)

import rapidjson as json

logger = logging.getLogger(__name__)


def default(obj: Any) -> Any:
    """For custom object serialization."""
    if isinstance(obj, Set):
        return {"__set__": True, "elements": sorted(obj)}
    raise TypeError(repr(obj) + " is not JSON serializable")


def object_hook(dct: dict) -> Any:
    """For custom object deserialization."""
    if "__set__" in dct:
        return set(dct["elements"])
    return dct


def dumps(
    obj: Any,
    sort_keys: bool = True,
    separators: Any = (",", ":"),
    default: "Callable[[Any], Any]" = default,
    **kwargs: Any,
) -> str:
    """Returns a JSON string from a Python object."""
    return json.dumps(
        obj,
        sort_keys=sort_keys,
        # separators=separators,
        default=default,
        indent=1,
        **kwargs,
    )


def dump(
    obj: Any,
    fp: IO[str],
    sort_keys: bool = True,
    separators: Any = (",", ":"),
    default: "Callable[[Any], Any]" = default,
    **kwargs: Any,
) -> None:
    """Returns a JSON string from a Python object."""
    return json.dump(
        obj,
        fp,
        sort_keys=sort_keys,
        # separators=separators,
        default=default,
        indent=1,
        **kwargs,
    )


def loads(
    s: str, object_hook: "Callable[[dict], Any]" = object_hook, **kwargs: Any
) -> dict:
    """Loads a string as JSON, with appropriate object hooks"""
    return json.loads(s, object_hook=object_hook, **kwargs)


def load(
    fp: IO[str],
    object_hook: "Callable[[dict], Any]" = object_hook,
    **kwargs: Any,
) -> dict:
    """Loads a file object as JSON, with appropriate object hooks."""
    return json.load(fp, object_hook=object_hook, **kwargs)
