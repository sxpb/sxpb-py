import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from sxpb.types import SxpbDict, SxpbLone, SxpbMany, SxpbNest


def dumps(obj: Any, indent: int = 1) -> str:
    """Serializes a Python object to an Sxpb string."""
    if isinstance(obj, SxpbNest):
        # Top-level Nest
        body = _serialize_nest_body(obj, indent, 0)
        if indent > 0:
            if "\n" not in body:
                return f'("")\n{body}'
            else:
                return f'("")\n{body}'
        else:
            return f'("") {body}'

    if isinstance(obj, SxpbDict):
        # Top-level Dict
        body = _serialize_message_body(obj, indent, 0)
        if not body:
            return "()"
        if indent > 0:
            return "()\n" + body
        if indent == 0:
            return "() " + body
        # indent < 0
        return "()" + body

    if isinstance(obj, Mapping):
        return _serialize_message_body(obj, indent, 0)

    if isinstance(obj, SxpbMany):
        # Top-level ManyOf
        if not obj:
            return "(())"
        parts = []
        for item in obj:
            parts.append(_serialize_message_body(item, indent, 0))

        if indent > 0:
            return "(())\n" + "\n".join(parts)
        if indent == 0:
            return "(()) " + " ".join(parts)

        # indent < 0
        return _join_condensed(["(())"] + parts)

    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
        # Top-level Array
        list_body = _serialize_list_body(obj, indent, 0)
        if not list_body:
            return "(())"

        if indent > 0:
            if "\n" not in list_body:
                return f"(()) {list_body}"
            return f"(())\n{list_body}"

        if indent == 0:
            return f"(()) {list_body}"

        # indent < 0
        return f"((){list_body})"

    raise TypeError("Top-level object must be a message or a list/array")


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


def _format_atom(
    v, in_array: bool = False, in_nest_string: bool = False, is_key: bool = False
):
    if isinstance(v, bool):
        return "+true" if v else "+false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if not s:
        return '""'
    if in_nest_string:
        pass

    # Keys cannot have spaces (unless quoted).
    if is_key and " " in s:
        return json.dumps(s, ensure_ascii=False)

    if in_array and " " in s:
        return json.dumps(s, ensure_ascii=False)

    if not _is_plain_string(s) or not _has_bare_prefix(s):
        return json.dumps(s, ensure_ascii=False)
    return s


def _format_nest_string(s: str) -> str:
    """Formats a string value for a nest field (after `""`)."""
    if not s:
        return ""  # empty string

    parts = s.split(" ")
    tokens = []

    for part in parts:
        is_bare = _is_plain_string(part) and _has_bare_prefix(part)
        token = part if is_bare else json.dumps(part, ensure_ascii=False)
        tokens.append((token, is_bare))

    if not tokens:
        return ""

    result = []
    for i, (token, is_bare) in enumerate(tokens):
        if i > 0:
            prev_token, prev_is_bare = tokens[i - 1]
            if prev_is_bare and is_bare:
                # Implicit space
                pass
            else:
                # Explicit space
                result.append('" "')
        result.append(token)

    return " ".join(result)


def _serialize_nest_body(nest: SxpbNest, indent: int, level: int) -> str:
    pad = " " * (indent * level) if indent > 0 else ""

    # "a nest of 1 to 3 strings should stay on the same line, but any more or any subnests cause each to be on their own line"
    all_strings = True
    leaves = []

    for item in nest:
        if isinstance(item, str):
            leaves.append(item)
        else:
            all_strings = False
            break

    should_condense = all_strings and len(leaves) >= 1 and len(leaves) <= 3

    parts = []
    for item in nest:
        # Handle formatting logic
        formatted_entry = ""

        if isinstance(item, str):
            key = item
            if not key:
                formatted_entry = '("" "")'
            else:
                key_has_spaces = " " in key
                if key_has_spaces:
                    # Use ("" key) syntax to allow bare words
                    formatted_key = _format_nest_string(key)
                    formatted_entry = f'("" {formatted_key})'
                else:
                    # Use simple bare key (quoted if special chars)
                    formatted_entry = _format_atom(key, is_key=True)

        elif isinstance(item, Mapping):
            # Dict with 1 key: sub-nest
            key, value = list(item.items())[0]

            if isinstance(value, SxpbNest):
                # Check for single-string optimization
                # Optimization: If sub-nest has 1 item K which is string.
                # If K has spaces, output (key "" K).
                # If K is simple, output (key K).

                if key == "":
                    # Anonymous nest: ("" ("") body)
                    # We must force the ("") discriminator
                    key_atom = '""'
                    body = _serialize_nest_body(value, indent, level + 1)
                    if indent > 0:
                        if "\n" not in body:
                            formatted_entry = f'({key_atom} ("") {body.lstrip()})'
                        else:
                            formatted_entry = f'({key_atom} ("")\n{body}\n{pad})'
                    else:
                        formatted_entry = f'({key_atom} ("") {body})'

                elif len(value) == 1 and isinstance(value[0], str):
                    sub_key = value[0]
                    if " " in sub_key:
                        sub_key_fmt = _format_nest_string(sub_key)
                        key_atom = _format_atom(key, is_key=True)
                        formatted_entry = f'({key_atom} "" {sub_key_fmt})'
                    else:
                        # Simple sub-key. (key sub_key)
                        key_atom = _format_atom(key, is_key=True)
                        sub_key_atom = _format_atom(sub_key, is_key=True)
                        formatted_entry = f"({key_atom} {sub_key_atom})"
                else:
                    # Recursive nest
                    key_atom = _format_atom(key, is_key=True)
                    # Recurse
                    body = _serialize_nest_body(value, indent, level + 1)

                    if indent > 0:
                        if "\n" not in body:
                            formatted_entry = f"({key_atom} {body.lstrip()})"
                        else:
                            formatted_entry = f"({key_atom}\n{body}\n{pad})"
                    else:
                        formatted_entry = f"({key_atom} {body})"
            else:
                # Should not happen given new parser logic, but fallback
                val_str = _format_nest_string(str(value))
                key_atom = _format_atom(key, is_key=True)
                formatted_entry = f'({key_atom} "" {val_str})'

        parts.append(formatted_entry)

    if should_condense:
        return " ".join(parts)

    if indent > 0:
        if parts:
            padded_parts = [f"{pad}{p}" for p in parts]
            return "\n".join(padded_parts)
    return " ".join(parts)


def _serialize_field(key: str, value: Any, indent: int, level: int) -> str:
    """Serializes a single key-value pair into a full Sxpb field string."""
    pad = " " * (indent * level) if indent > 0 else ""

    if isinstance(value, SxpbNest):
        body = _serialize_nest_body(value, indent, level + 1)
        if indent > 0:
            if "\n" not in body:
                return f'{pad}({key} ("") {body.lstrip()})'
            else:
                return f'{pad}({key} ("")\n{body}\n{pad})'
        else:
            return f'({key} ("") {body})'

    if isinstance(value, SxpbMany):
        if not value:
            return f"{pad}(({key}))"

        parts = []
        for item in value:
            if isinstance(item, SxpbLone) and "value" in item and len(item) == 1:
                val = item["value"]
                if indent > 0:
                    inner_pad = " " * (indent * (level + 1))
                    parts.append(f"{inner_pad}{_format_atom(val, in_array=True)}")
                else:
                    parts.append(_format_atom(val, in_array=True))
            else:
                parts.append(_serialize_message_body(item, indent, level + 1))

        if indent > 0:
            body = "\n".join(parts)
            return f"{pad}(({key})\n{body}\n{pad})"

        if indent == 0:
            body = " ".join(parts)
            return f"(({key}) {body})"

        # indent < 0
        body = _join_condensed(parts)
        return f"(({key}){body})"

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

    if isinstance(value, SxpbDict):
        body = _serialize_message_body(value, indent, level + 1)
        if not body:
            return f"{pad}({key} ())"
        if indent > 0:
            return f"{pad}({key} ()\n{body}\n{pad})"

        joiner = " " if indent == 0 else ""
        return f"({key}{joiner}(){joiner}{body})"

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
