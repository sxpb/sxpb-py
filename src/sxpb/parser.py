import re
import textwrap
from collections import UserList
from pathlib import Path
from typing import Any, Dict, List, Union

import lark
from lark import Lark, Token, Transformer, v_args

from .jsonutil import to_plain_types
from .types import SxpbDict, SxpbList, SxpbLone, SxpbMany

GRAMMAR = (Path(__file__).parent / "grammar.lark").read_text()
LARK_GRAMMAR_PATH = str(Path(lark.__file__).parent / "grammars")
NUM_INT = re.compile(r"^[+-]?\d+$")
NUM_FLOAT = re.compile(r"^[+-]?(?:\d*\.\d+|\d+\.\d*)(?:[eE][+-]?\d+)?$")

Json = Union[Dict[str, Any], List[Any], str, int, float, bool, None]


class UnquotedString(str):
    pass


class SexpTransformer(Transformer):
    def BARE(self, s):
        return UnquotedString(s.value)

    def PLAIN(self, s):
        return UnquotedString(s.value)

    @v_args(inline=True)
    def BOOLEAN(self, b):
        return b.value == "+true"

    @v_args(inline=True)
    def SIGNED_NUMBER(self, n):
        if NUM_INT.match(n.value):
            return int(n.value)
        if NUM_FLOAT.match(n.value):
            return float(n.value)
        return n.value

    def NONEMPTY_ESCAPED_STRING(self, s):
        return s.value[1:-1]

    def ESCAPED_STRING(self, s):
        return s.value[1:-1]

    def MULTILINE_STRING(self, s):
        val = s.value[3:-3]
        if val.startswith("\\\n"):
            val = val[2:]
        elif val.startswith("\n"):
            val = val[1:]
        val = textwrap.dedent(val)
        val = val.replace('\\"', '"')
        return val

    @v_args(inline=True)
    def manyof_item(self, a):
        return a

    @v_args(inline=True)
    def field_name(self, a):
        if isinstance(a, UnquotedString):
            return str(a)
        return a

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
        if isinstance(val, UnquotedString):
            return str(val)
        return val

    def message_body(self, fields):
        message = SxpbDict()
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
        name = items[0]
        if len(items) == 1:
            return name, SxpbMany()

        body = items[1:]
        if not body:
            return name, SxpbMany()

        # `body` can be a list from manyof_body, or a Token from atom+, or a tuple from any_field*
        if isinstance(body[0], SxpbMany):  # manyof_body
            return name, body[0]

        # The body is from (atom | any_field)*
        new_body = []
        for item in body:
            if isinstance(item, tuple):
                new_body.append(SxpbLone({item[0]: item[1]}))
            else:
                new_body.append(SxpbLone({"value": item}))
        return name, SxpbMany(new_body)

    def loneof_name(self, items):
        return items

    def manyof_body(self, items):
        return SxpbMany([SxpbLone({item[0]: item[1]}) for item in items])

    def any_field(self, items):
        return items[0]

    def empty_message(self, _):
        return SxpbDict()

    def unnamed_message_field(self, items):
        if len(items) == 2:
            return items[1]
        return items[0]

    def unquoted_array_string(self, items):
        return " ".join(str(i) for i in items)

    def string_array(self, items):
        # The transformer has already processed the terminal tokens into strings or UnquotedString objects.
        # Per the project's requirements, if any element in an array is a string, all elements are converted to strings.
        # Since all children of the `string_array` rule are string-like, we just convert them all.
        return SxpbList([str(item) for item in items])

    def array_body(self, items):
        # The grammar rule for array_body is now `"(())" (unnamed_message_field* | SIGNED_NUMBER* | BOOLEAN* | string_array)`.
        # The items will either be a list of messages, a list of numbers, a list of booleans, or a single SxpbList from string_array.
        if items and isinstance(items[0], SxpbList):
            # This is a string array that has been processed by string_array
            return items[0]
        if items and isinstance(items[0], Token) and items[0].type == "SIGNED_NUMBER":
            return SxpbList([self.SIGNED_NUMBER(i) for i in items])
        if items and isinstance(items[0], Token) and items[0].type == "BOOLEAN":
            return SxpbList([self.BOOLEAN(i) for i in items])
        # It's an array of messages or an empty array
        return SxpbList(items)


sxpb_parser = Lark(GRAMMAR, start="start", import_paths=[LARK_GRAMMAR_PATH])


def loads(text: str, builtin_only: bool = False) -> Json:
    tree = sxpb_parser.parse(text)
    data = SexpTransformer().transform(tree)
    if builtin_only:
        return to_plain_types(data)
    return data


def load(path: str, builtin_only: bool = False) -> Json:
    with open(path, "r", encoding="utf-8") as f:
        return loads(f.read(), builtin_only=builtin_only)
