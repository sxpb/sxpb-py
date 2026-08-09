import json
import re
from collections import UserList
from pathlib import Path
from typing import Any, Union

import lark
from lark import Lark, Token, Transformer, v_args
from lark.exceptions import LarkError

from sxpb.exceptions import SxpbParseError
from sxpb.jsonutil import to_plain_types
from sxpb.types import SxpbDict, SxpbList, SxpbLone, SxpbMany, SxpbMesg, SxpbNest

GRAMMAR = (Path(__file__).parent / "grammar.lark").read_text()
LARK_GRAMMAR_PATH = str(Path(str(lark.__file__)).parent / "grammars")
NUM_INT = re.compile(r"^[+-]?\d+$")
NUM_FLOAT = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?$")

Json = Union[dict[str, Any], list[Any], str, int, float, bool, None]

_TOKEN_TRANSLATIONS = {
    "BARE": "an unquoted word (e.g., key_name)",
    "BOOLEAN": "a boolean (+true or +false)",
    "EMPTY_STRING": "an empty quoted string",
    "ESCAPED_STRING": 'a quoted string (e.g., "hello world")',
    "LPAR": "an opening parenthesis `(`",
    "MULTILINE_STRING": 'a multiline string (e.g., """...""")',
    "NONEMPTY_ESCAPED_STRING": 'a quoted string (e.g., "hello world")',
    "PLAIN": "an unquoted string",
    "RPAR": "a closing parenthesis `)`",
    "SIGNED_NUMBER": "a number (e.g., 123, -4.5, +1e6)",
}


def _format_lark_error(error: Any, text: str) -> str:
    expected_tokens = getattr(error, "expected", getattr(error, "allowed", None))
    if hasattr(error, "char"):
        token = getattr(error, "token", None)
        found = (
            f"'{token.value}'"
            if token
            else f"character '{getattr(error, 'char', '?')}'"
        )
        message = f"Found an unexpected {found}."
    else:
        message = "Unexpected end of input."

    get_context = getattr(error, "get_context", None)
    context = get_context(text) if callable(get_context) else ""
    if context:
        message += f"\n\n{context}"

    if expected_tokens:
        message += "\n\nExpected one of the following:\n"
        for token_name in sorted(expected_tokens):
            description = _TOKEN_TRANSLATIONS.get(token_name, token_name)
            message += f"  - {description}\n"
    return message


_SIMPLE_ESCAPE_VALUES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
}


def _decode_quoted_content(content: str) -> str:
    result: list[str] = []
    i = 0
    while i < len(content):
        char = content[i]
        if char == "\r":
            i += 1
            continue
        if char != "\\":
            result.append(char)
            i += 1
            continue
        if i + 1 >= len(content):
            raise ValueError("Unterminated escape sequence in quoted string")

        escaped = content[i + 1]
        if escaped == "\n":
            i += 2
            continue
        if escaped == "\r" and i + 2 < len(content) and content[i + 2] == "\n":
            i += 3
            continue
        if escaped in _SIMPLE_ESCAPE_VALUES:
            result.append(_SIMPLE_ESCAPE_VALUES[escaped])
            i += 2
            continue
        if escaped == "u" and i + 6 <= len(content):
            end = i + 6
            first_codepoint = int(content[i + 2 : end], 16)
            if (
                0xD800 <= first_codepoint <= 0xDBFF
                and content.startswith("\\u", end)
                and end + 6 <= len(content)
            ):
                end += 6
            result.append(json.loads(f'"{content[i:end]}"'))
            i = end
            continue
        raise ValueError(f"Unknown escape sequence: \\{escaped}")
    return "".join(result)


class UnquotedString(str):
    pass


class ScalarAtom:
    """Parsed scalar value with source spelling retained for list reconciliation."""

    def __init__(self, value: int | float | bool, spelling: str, line: int) -> None:
        self.value = value
        self.spelling = spelling
        self.line = line


def _normalize_scalar_list(items, *, kind):
    """Reconcile scalar elements using the first element's literal kind."""
    normalized = []
    for item in items:
        if not isinstance(item, ScalarAtom):
            normalized.append(str(item) if isinstance(item, UnquotedString) else item)
            continue
        if kind == "string":
            normalized.append(item.spelling)
        elif kind == "number":
            normalized.append(item.value)
        elif isinstance(item.value, bool):
            normalized.append(item.value)
        elif (
            isinstance(item.value, int)
            and not item.spelling.startswith("-")
            and item.value in (0, 1)
        ):
            normalized.append(bool(item.value))
        elif isinstance(item.value, int):
            raise SxpbParseError(f"Line {item.line}: Expected a bool, not an int.")
        else:
            raise SxpbParseError(f"Line {item.line}: Unexpected literal type.")
    return SxpbList(normalized)


def _as_manyof_element(item: Any) -> Any:
    if isinstance(item, tuple):
        return SxpbLone({item[0]: item[1]})
    if isinstance(item, (SxpbLone, SxpbMany)):
        return item
    return SxpbLone({"": item})


def _normalize_manyof_body(items, *, kind=None):
    """Normalize only anonymous elements; named elements are transparent."""
    if kind is None or kind == "message":
        normalized_anonymous = iter(
            item for item in items if not isinstance(item, tuple)
        )
    else:
        anonymous = [item for item in items if not isinstance(item, tuple)]
        normalized_anonymous = iter(_normalize_scalar_list(anonymous, kind=kind))

    normalized = []
    for item in items:
        if not isinstance(item, tuple):
            item = next(normalized_anonymous)
        normalized.append(_as_manyof_element(item))
    return SxpbMany(normalized)


class SexpTransformer(Transformer):
    def BARE(self, s):
        return UnquotedString(s.value)

    def PLAIN(self, s):
        return UnquotedString(s.value)

    def SUBNEST_PLAIN_NAME(self, s):
        return str(s)

    @v_args(inline=True)
    def BOOLEAN(self, b):
        return ScalarAtom(b.value == "+true", b.value, b.line)

    @v_args(inline=True)
    def SIGNED_NUMBER(self, n):
        if NUM_INT.match(n.value):
            return ScalarAtom(int(n.value), n.value, n.line)
        if NUM_FLOAT.match(n.value):
            return ScalarAtom(float(n.value), n.value, n.line)
        return n.value

    def NONEMPTY_ESCAPED_STRING(self, s):
        return _decode_quoted_content(s.value[1:-1])

    def ESCAPED_STRING(self, s):
        return _decode_quoted_content(s.value[1:-1])

    def MULTILINE_STRING(self, s):
        return _decode_quoted_content(s.value[3:-3])

    @v_args(inline=True)
    def field_name(self, a):
        if isinstance(a, UnquotedString):
            return str(a)
        return a

    @v_args(inline=True)
    def subnest_name(self, name):
        return name

    def string_body(self, atoms):
        string_parts = []
        for i, v in enumerate(atoms):
            string_parts.append(v)
            if i + 1 < len(atoms):
                is_unquoted = isinstance(v, UnquotedString)
                next_v = atoms[i + 1]
                next_is_unquoted = isinstance(next_v, UnquotedString)
                if is_unquoted and next_is_unquoted:
                    string_parts.append(" ")
        return "".join(string_parts)

    def scalar_body(self, items):
        val = items[0]
        if isinstance(val, ScalarAtom):
            return val.value
        if isinstance(val, UnquotedString):
            return str(val)
        return val

    def message_body(self, fields):
        message = SxpbMesg()
        for key, val in fields:
            if key in message:
                if not isinstance(message[key], UserList):
                    message[key] = SxpbList([message[key]])
                if isinstance(val, UserList):
                    message[key].extend(val)
                else:
                    message[key].append(val)
            else:
                message[key] = val
        return message

    def nonempty_message_body(self, fields):
        return self.message_body(fields)

    @v_args(inline=True)
    def start(self, body):
        return body

    def regular_field(self, items):
        key, value = items
        return key, value

    def loneof_field(self, items):
        loneof_name, value = items
        key, subkey = loneof_name
        return key, SxpbLone({subkey: value})

    def manyof_field(self, items):
        name, body = items
        return name, body

    def loneof_name(self, items):
        return items

    def discriminated_dict(self, items):
        # items[0] is DICT_DISCRIM, items[1] is message_body
        return SxpbDict(items[1])

    def discriminated_manyof(self, items):
        # The required first named element establishes the manyof but does not
        # participate in anonymous element-kind reconciliation.
        start_idx = 0
        if items and isinstance(items[0], Token) and items[0].type == "LIST_DISCRIM":
            start_idx = 1
        first_item = _as_manyof_element(items[start_idx])
        body = items[start_idx + 1]
        return SxpbMany([first_item, *body])

    def manyof_body(self, items):
        return items[0]

    def named_manyof_body(self, items):
        return _normalize_manyof_body(items)

    def message_manyof_item(self, items):
        return items[0]

    def message_manyof_tail(self, items):
        return items[0]

    def string_manyof_tail(self, items):
        return items[0]

    def number_manyof_tail(self, items):
        return items[0]

    def boolean_manyof_tail(self, items):
        return items[0]

    def message_manyof_body(self, items):
        return _normalize_manyof_body(items, kind="message")

    def string_manyof_body(self, items):
        return _normalize_manyof_body(items, kind="string")

    def number_manyof_body(self, items):
        return _normalize_manyof_body(items, kind="number")

    def boolean_manyof_body(self, items):
        return _normalize_manyof_body(items, kind="bool")

    def any_field(self, items):
        return items[0]

    def empty_message(self, _):
        return SxpbMesg()

    def anonymous_discriminated_message(self, items):
        # items: [empty_message_result, message_body_result] -> [{}, dict]
        return items[1]

    def message_array_body(self, items):
        # items: list of dicts (from empty_message or anonymous_discriminated_message)
        return SxpbList(items)

    def discriminated_string(self, items):
        # items[0] is STRING_DISCRIM (marker)
        # items[1:] is content
        return self.string_body(items[1:])

    def anonymous_discriminated_string(self, items):
        return self.string_body(items[1:])

    def string_array_starter(self, items):
        return items[0]

    def string_array_item(self, items):
        return items[0]

    def string_array_body(self, items):
        return _normalize_scalar_list(items, kind="string")

    def number_array_body(self, items):
        return _normalize_scalar_list(items, kind="number")

    def boolean_array_body(self, items):
        return _normalize_scalar_list(items, kind="bool")

    def discriminated_array(self, items):
        # items[0] is LIST_DISCRIM, items[1] is array_body result
        return items[1]

    def array_body(self, items):
        if items and isinstance(items[0], SxpbList):
            return items[0]
        return SxpbList(items)

    def discriminated_nest(self, items):
        # items: [NEST_DISCRIM, nest_body]
        return items[-1]

    def nest_body(self, items):
        return SxpbNest(items)

    def nest_item(self, items):
        return items[0]

    @v_args(inline=True)
    def nest_leaf(self, leaf: str) -> str:
        if isinstance(leaf, UnquotedString):
            return str(leaf)
        return leaf

    def nest_subfield(self, items):
        # items: [subnest_name, nest_body]
        key = items[0]
        body = items[-1]
        return SxpbLone({key: body})

    def anonymous_discriminated_nest(self, items):
        # items: [NEST_DISCRIM, nest_body]
        # Wrap the list returned by nest_body in SxpbNest
        # Return as SxpbLone with empty key to match JSON representation and handle serialization
        return SxpbLone({"": SxpbNest(items[-1])})

    def discriminated_string_nest_subfield(self, items):
        # items: [subnest_name, discriminated_string]
        # discriminated_string already returns string
        key = items[0]
        content = items[1]
        return SxpbLone({key: SxpbNest([content])})


sxpb_parser = Lark(GRAMMAR, start="start", import_paths=[LARK_GRAMMAR_PATH])


def loads(text: str, precise: bool = False) -> Json:
    try:
        tree = sxpb_parser.parse(text)
        data = SexpTransformer().transform(tree)
    except LarkError as e:
        raise SxpbParseError(_format_lark_error(e, text)) from e
    if not precise:
        return to_plain_types(data)
    return data


def load(path: str, precise: bool = False) -> Json:
    with open(path, "r", encoding="utf-8") as f:
        return loads(f.read(), precise=precise)
