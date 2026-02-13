import re
import textwrap
import json
from collections import UserList
from pathlib import Path
from typing import Any, Dict, List, Union

import lark
from lark import Lark, Token, Transformer, v_args

from .jsonutil import to_plain_types
from .types import SxpbDict, SxpbList, SxpbLone, SxpbMany, SxpbNest

GRAMMAR = (Path(__file__).parent / "grammar.lark").read_text()
LARK_GRAMMAR_PATH = str(Path(str(lark.__file__)).parent / "grammars")
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
        # Uses json.loads to properly unescape string
        return json.loads(s.value)

    def ESCAPED_STRING(self, s):
        # Uses json.loads to properly unescape string
        return json.loads(s.value)

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

        # `body` can be a list from discriminated_manyof (result is SxpbMany),
        # or a Token from atom+, or a tuple from any_field*
        if isinstance(body[0], SxpbMany):  # discriminated_manyof
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

    def discriminated_manyof(self, items):
        # items[0] might be LIST_DISCRIM if it's passed through
        start_idx = 0
        if items and isinstance(items[0], Token) and items[0].type == "LIST_DISCRIM":
            start_idx = 1

        # Filter out remaining items
        items = items[start_idx:]

        return SxpbMany([SxpbLone({item[0]: item[1]}) for item in items])

    def any_field(self, items):
        return items[0]

    def empty_message(self, _):
        return SxpbDict()

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

    def string_array_body(self, items):
        # The transformer has already processed the terminal tokens into strings or UnquotedString objects.
        # Per the project's requirements, if any element in an array is a string, all elements are converted to strings.
        # Since all children of the `string_array_body` rule are string-like, we just convert them all.
        return SxpbList([str(item) for item in items])

    def discriminated_array(self, items):
        # items[0] is LIST_DISCRIM, items[1] is array_body result
        return items[1]

    def array_body(self, items):
        # The items will either be:
        # 1. A single SxpbList from message_array_body
        # 2. A single SxpbList from string_array_body
        # 3. A list of numbers or booleans (directly in items)

        if items and isinstance(items[0], SxpbList):
            # Case 1 or 2
            return items[0]

        # Case 3 (or empty fallthrough)
        if items and isinstance(items[0], Token) and items[0].type == "SIGNED_NUMBER":
            return SxpbList([self.SIGNED_NUMBER(i) for i in items])
        if items and isinstance(items[0], Token) and items[0].type == "BOOLEAN":
            return SxpbList([self.BOOLEAN(i) for i in items])

        # Fallback for empty array or heterogenous (if grammar allowed it, which it doesn't really)
        # If empty, items is empty list here.
        return SxpbList(items)

    def discriminated_nest(self, items):
        # items: [NEST_DISCRIM, nest_body]
        return items[-1]

    def nest_body(self, items):
        return SxpbNest(items)

    def nest_item(self, items):
        # items[0] is the result of nest_key | nest_subfield | discriminated_string_field
        return items[0]

    @v_args(inline=True)
    def nest_key(self, k: str) -> str:
        # k can be UnquotedString (BARE) or str (ESCAPED_STRING etc)
        if isinstance(k, UnquotedString):
            k = str(k)
        # anonymous_discriminated_string logic returns joined string, passed as is
        return k

    def nest_subfield(self, items):
        # items: [field_name, nest_body]
        key = items[0]
        body = items[-1]
        return SxpbLone({key: body})

    def anonymous_discriminated_nest(self, items):
        # items: [NEST_DISCRIM, nest_body]
        # Wrap the list returned by nest_body in SxpbNest
        # Return as SxpbLone with empty key to match JSON representation and handle serialization
        return SxpbLone({"": SxpbNest(items[-1])})

    def discriminated_string_field(self, items):
        # items: [field_name, discriminated_string]
        # discriminated_string already returns string
        key = items[0]
        content = items[1]
        return SxpbLone({key: SxpbNest([content])})


sxpb_parser = Lark(GRAMMAR, start="start", import_paths=[LARK_GRAMMAR_PATH])


def loads(text: str, precise: bool = False) -> Json:
    tree = sxpb_parser.parse(text)
    data = SexpTransformer().transform(tree)
    if not precise:
        return to_plain_types(data)
    return data


def load(path: str, precise: bool = False) -> Json:
    with open(path, "r", encoding="utf-8") as f:
        return loads(f.read(), precise=precise)
