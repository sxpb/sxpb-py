import json
from typing import Any
from collections import UserDict, UserList


def to_json(obj: Any, path: str, **kwargs):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, **kwargs)


def from_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def to_plain_types(data):
    if hasattr(data, "to_dict"):
        return data.to_dict()
    if hasattr(data, "to_list"):
        return data.to_list()
    if isinstance(data, UserDict):
        return {k: to_plain_types(v) for k, v in data.items()}
    if isinstance(data, UserList):
        return [to_plain_types(v) for v in data]
    return data
