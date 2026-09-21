from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def clone_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return deepcopy(value)
    return value


def values_equal(left: Any, right: Any) -> bool:
    return jsonable(left) == jsonable(right)


def field_changes(before: dict, after: dict, fields: tuple[str, ...] | None = None) -> dict[str, dict[str, Any]]:
    keys = fields if fields is not None else tuple(sorted(set(before) | set(after)))
    changes: dict[str, dict[str, Any]] = {}
    for key in keys:
        old = before.get(key)
        new = after.get(key)
        if values_equal(old, new):
            continue
        changes[key] = {"before": jsonable(old), "after": jsonable(new)}
    return changes
