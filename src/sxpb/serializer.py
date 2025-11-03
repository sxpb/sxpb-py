import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from sxpb.types import SxpbLone, SxpbMany


def dumps(obj: Any, indent: int = 1) -> str:
    """Serializes a Python object to an Sxpb string."""
    if isinstance(obj, Mapping):
        return _serialize_message_body(obj, indent, 0)
    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
        # This handles top-level lists, like in manyof.sxpb
        if not obj:
            return "(())"
        parts = []
        for item in obj:
            parts.append(_serialize_message_body(item, indent, 0))

        if indent > 0:
            return "\n".join(parts)
        if indent == 0:
            return " ".join(parts)

        # indent < 0
        return _join_condensed(parts)

    raise TypeError("Top-level object must be a message/dict or a list/array")


def dump(obj: Any, path: str, indent: int = 1):
    """Serializes a Python object to an Sxpb file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(dumps(obj, indent=indent))


def _join_condensed(parts: list[str]) -> str:
    if not parts:
        return ""

    parts = [p for p in parts if p]
    if not parts:
        return ""

    result = [parts[0]]
    for i in range(1, len(parts)):
        prev = result[-1]
        curr = parts[i]
        if (
            prev.endswith("(")
            or prev.endswith(")")
            or curr.startswith("(")
            or curr.startswith(")")
        ):
            result.append(curr)
        else:
            result.append(" ")
            result.append(curr)
    return "".join(result)


# A string is "plain" if all of its characters match this regex.
_PLAIN_STRING_RE = re.compile(r"^[^\t\n\v\f\r;\"()]+$")


def _is_plain_string(s: str) -> bool:
    """Checks if a string consists entirely of 'plain' characters."""
    if not s:
        return False
    return bool(_PLAIN_STRING_RE.match(s))


# This regex matches strings that have a valid BARE prefix according to the grammar.
_BARE_PREFIX_RE = re.compile(
    r"^([-.]?[^-+.0123456789 \t\n\v\f\r;\"()]|[-][-]|[.][.]|[-]$|[.]$)"
)


def _has_bare_prefix(s: str) -> bool:
    """
    Checks if a string starts with a prefix that is valid for a BARE atom.
    If not, it must be quoted to avoid being parsed as a number, boolean, etc.
    """
    if not s:
        return False
    return bool(_BARE_PREFIX_RE.match(s))


def _format_atom(v, in_array: bool = False):
    if isinstance(v, bool):
        return "+true" if v else "+false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if not s:
        return '""'
    if in_array and " " in s:
        return json.dumps(s, ensure_ascii=False)
    if not _is_plain_string(s) or not _has_bare_prefix(s):
        return json.dumps(s, ensure_ascii=False)
    return s


def _serialize_field(key: str, value: Any, indent: int, level: int) -> str:
    """Serializes a single key-value pair into a full Sxpb field string."""
    pad = " " * (indent * level) if indent > 0 else ""

    if isinstance(value, SxpbMany) and not value:
        return f"{pad}(({key}))"

    if isinstance(value, SxpbLone):
        subkey, lone_value = list(value.items())[0]
        if isinstance(lone_value, Mapping):
            body = _serialize_message_body(lone_value, indent, level + 1)
            if indent > 0:
                return (
                    f"{pad}(({key} {subkey})\n{body}\n{pad})"
                    if body
                    else f"{pad}(({key} {subkey}))"
                )
            key_part = (
                f"({key} {subkey})"
                if indent == 0
                else f"({_join_condensed([key, subkey])})"
            )
            return f"(({_join_condensed([key_part, body])}))"
        else:
            if indent > 0:
                return f"{pad}(({key} {subkey}) {_format_atom(lone_value)})"
            key_part = (
                f"({key} {subkey})"
                if indent == 0
                else f"({_join_condensed([key, subkey])})"
            )
            return f"(({_join_condensed([key_part, _format_atom(lone_value)])}))"

    if isinstance(value, Mapping):
        body = _serialize_message_body(value, indent, level + 1)
        if not body:
            return f"{pad}({key})"
        if indent > 0:
            return f"{pad}({key}\n{body}\n{pad})"
        joiner = " " if indent == 0 or (indent < 0 and not body.startswith("(")) else ""
        return f"({key}{joiner}{body})"

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        list_body = _serialize_list_body(value, indent, level + 1)
        if indent > 0:
            return (
                f"{pad}({key} (())\n{list_body}\n{pad})"
                if list_body
                else f"{pad}({key} (()))"
            )

        joiner = "" if indent < 0 else " "
        return f"({key}{joiner}(()){joiner}{list_body})"

    if indent > 0:
        return f"{pad}({key} {_format_atom(value)})"
    return f"({key} {_format_atom(value)})"


def _serialize_list_body(lst: Sequence, indent: int, level: int) -> str:
    is_message_array = lst and isinstance(lst[0], Mapping)

    if is_message_array and indent < 0:
        bodies = [_serialize_message_body(item, indent, level + 1) for item in lst]
        return f"((){_join_condensed(bodies)})"

    items = []
    for item in lst:
        if is_message_array:
            body = _serialize_message_body(item, indent, level + 1)
            if indent > 0:
                pad = " " * (indent * level)
                items.append(f"{pad}(()\n{body}\n{pad})" if body else f"{pad}()")
            else:  # indent == 0
                items.append(f"(() {body})" if body else "()")
        else:  # scalar array
            if indent > 0:
                pad = " " * (indent * level)
                items.append(f"{pad}{_format_atom(item, in_array=True)}")
            else:
                items.append(_format_atom(item, in_array=True))

    return "\n".join(items) if indent > 0 else " ".join(items)


def _serialize_message_body(d: Mapping, indent: int, level: int) -> str:
    parts = [_serialize_field(k, v, indent, level) for k, v in d.items()]

    if indent > 0:
        return "\n".join(parts)
    if indent == 0:
        return " ".join(parts)
    return _join_condensed(parts)
