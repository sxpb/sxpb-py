import json
from collections import UserDict, UserList
from collections.abc import Mapping
from typing import Any

from .types import SxpbMany


def to_json(obj: Any, path: str, **kwargs):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_plain_types(obj), f, **kwargs)


def from_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def to_plain_types(data):
    """Convert precise SxPB containers to JSON/YAML-compatible builtins."""
    if isinstance(data, SxpbMany):
        elements = []
        for item in data:
            if isinstance(item, Mapping) and len(item) == 1 and "" in item:
                elements.append({"value": to_plain_types(item[""])})
            else:
                elements.append(to_plain_types(item))
        return elements
    if isinstance(data, (UserDict, dict)):
        return {k: to_plain_types(v) for k, v in data.items()}
    if isinstance(data, (UserList, list)):
        return [to_plain_types(v) for v in data]
    if hasattr(data, "to_dict"):
        return to_plain_types(data.to_dict())
    if hasattr(data, "to_list"):
        return to_plain_types(data.to_list())
    return data
