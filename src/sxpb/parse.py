"""Hand-rolled recursive descent parser for SxPB.

Mirrors test/reference_parser/grammar.lark rule-for-rule.
Produces SxPB types directly (SxpbDict, SxpbList, SxpbLone, SxpbMany, SxpbNest)
without an intermediate parse tree or transformer.

~100x faster than the Lark Earley parser.
"""

from __future__ import annotations

import json
import re
from collections import UserList
from typing import Any, Union, cast

from .exceptions import SxpbParseError
from .jsonutil import to_plain_types
from .types import SxpbDict, SxpbList, SxpbLone, SxpbMany, SxpbMesg, SxpbNest

Json = Union[dict[str, Any], list[Any], str, int, float, bool, None]

# ── tokenizer ────────────────────────────────────────────────────────────────

# Character classification
_WS = frozenset(" \t\n\r\f\v")
_ATOM_END = _WS | frozenset('();"')


class _Token:
    """Lightweight token — just a (type, value, line) triple."""

    __slots__ = ("kind", "value", "line")

    def __init__(self, kind: str, value: Any, line: int) -> None:
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self) -> str:
        return f"Token({self.kind!r}, {self.value!r}, L{self.line})"


# Token kinds matching grammar terminal names
LPAREN = "LPAREN"
RPAREN = "RPAREN"
DICT_DISCRIM = "DICT_DISCRIM"  # ()
LIST_DISCRIM = "LIST_DISCRIM"  # (())
NEST_DISCRIM = "NEST_DISCRIM"  # ("")
STRING_DISCRIM = "STRING_DISCRIM"  # ""
BARE = "BARE"  # unquoted word (starts with non-digit/special)
PLAIN = "PLAIN"  # any non-whitespace, non-paren chars
QUOTED_STRING = "QUOTED_STRING"  # "..." (JSON-escaped)
MULTILINE_STRING = "MULTILINE_STRING"  # """..."""
NUMBER = "SIGNED_NUMBER"  # Raw numeric spelling; converted only in scalar contexts.
BOOLEAN = "BOOLEAN"  # Raw +true or +false spelling; converted only as a scalar.
END = "END"  # end of input


# Pre-compiled patterns for the tokenizer
_RE_NUMBER = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")
_RE_LIST_DISCRIM = re.compile(r"\(\s*\(\s*\)\s*\)")
_RE_NEST_DISCRIM = re.compile(r'\(\s*""\s*\)')
_RE_DICT_DISCRIM = re.compile(r"\(\s*\)")
# Keep this prefix logic in parity with Fildesh's has_sxpb_bare_prefix().
_RE_BARE = re.compile(
    r"^(--[^ \t\n\v\f\r;\"()]*|\.\.[^ \t\n\v\f\r;\"()]*|-|\.|"
    r"[-.]?[^-+.0123456789 \t\n\v\f\r;\"()][^ \t\n\v\f\r;\"()]*)$"
)
_RE_PLAIN = re.compile(r"^[^\t\n\v\f\r;\"()]+$")


def _has_sxpb_special_prefix(s: str) -> bool:
    """Match Fildesh's has_sxpb_special_prefix() exactly."""
    if not s:
        return False
    if s[0] == "+":
        return True
    if s[0] in "-.":
        if len(s) == 1 or s[0] == s[1]:
            return False
        return s[1] in "+-."
    return False


def _number_from_spelling(spelling: str) -> int | float:
    if re.fullmatch(r"[+-]?\d+", spelling):
        return int(spelling)
    return float(spelling)


def _boolean_from_spelling(spelling: str) -> bool:
    return spelling == "+true"


class _SxpbSyntaxError(SxpbParseError):
    """Parse error with line number context."""

    def __init__(self, msg: str, line: int, near: str = "") -> None:
        self.line = line
        self.near = near
        super().__init__(msg)


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
    """Decode quoted content with the same rules as the grammar parser."""
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


def _tokenize(text: str):
    """Yield tokens from SxPB source text.

    Tokenizer processes characters directly.  Discriminators like ``()``,
    ``(())``, ``(\"\")``, and ``\"\"`` are recognized as single tokens by
    peeking ahead, which mirrors the priority behaviour of the Lark regex
    terminals.
    """
    pos = 0
    n = len(text)
    line = 1

    while pos < n:
        ch = text[pos]

        # Whitespace
        if ch in _WS:
            if ch == "\n":
                line += 1
            pos += 1
            continue

        # Comment
        if ch == ";":
            while pos < n and text[pos] != "\n":
                pos += 1
            continue

        # Discriminators tolerate whitespace internally, but not comments.
        if ch == "(":
            for kind, pattern in (
                (LIST_DISCRIM, _RE_LIST_DISCRIM),
                (NEST_DISCRIM, _RE_NEST_DISCRIM),
                (DICT_DISCRIM, _RE_DICT_DISCRIM),
            ):
                match = pattern.match(text, pos)
                if match is not None:
                    lexeme = match.group()
                    yield _Token(kind, None, line)
                    line += lexeme.count("\n")
                    pos = match.end()
                    break
            else:
                match = None
            if match is not None:
                continue

        # STRING_DISCRIM: ""
        if (
            ch == '"'
            and pos + 1 < n
            and text[pos + 1] == '"'
            and (pos + 2 >= n or text[pos + 2] != '"')
        ):
            yield _Token(STRING_DISCRIM, None, line)
            pos += 2
            continue

        # Structural parens
        if ch == "(":
            yield _Token(LPAREN, None, line)
            pos += 1
            continue
        if ch == ")":
            yield _Token(RPAREN, None, line)
            pos += 1
            continue

        # Multiline string: """..."""
        if ch == '"' and pos + 2 < n and text[pos : pos + 3] == '"""':
            pos += 3  # skip opening """
            start = pos
            while pos + 2 < n and text[pos : pos + 3] != '"""':
                if text[pos] == "\n":
                    line += 1
                pos += 1
            if pos + 2 >= n:
                raise _SxpbSyntaxError(
                    "Unterminated multiline string", line, text[start : start + 20]
                )
            raw = text[start:pos]
            pos += 3  # skip closing """
            try:
                value = _decode_quoted_content(raw)
            except ValueError as e:
                raise _SxpbSyntaxError(str(e), line, raw[:20]) from e
            yield _Token(MULTILINE_STRING, value, line)
            continue

        # Quoted string: "..." (JSON-style escaping)
        if ch == '"':
            pos += 1  # skip opening quote
            start = pos
            while pos < n and text[pos] != '"':
                if text[pos] == "\\" and pos + 1 < n:
                    pos += 2  # skip escape sequence
                else:
                    if text[pos] == "\n":
                        line += 1
                    pos += 1
            if pos >= n:
                raise _SxpbSyntaxError(
                    "Unterminated quoted string", line, text[start - 1 : start + 20]
                )
            raw = text[start:pos]
            pos += 1  # skip closing quote
            try:
                value = _decode_quoted_content(raw)
            except ValueError as e:
                raise _SxpbSyntaxError(str(e), line, raw[:20]) from e
            yield _Token(QUOTED_STRING, value, line)
            continue

        # Boolean: +true or +false. Require an atom boundary so malformed
        # values such as +trueish are not tokenized as a boolean plus a word.
        if ch == "+":
            if text.startswith("+true", pos) and (
                pos + 5 == n or text[pos + 5] in _ATOM_END
            ):
                yield _Token(BOOLEAN, "+true", line)
                pos += 5
                continue
            if text.startswith("+false", pos) and (
                pos + 6 == n or text[pos + 6] in _ATOM_END
            ):
                yield _Token(BOOLEAN, "+false", line)
                pos += 6
                continue

        # Number or signed atom: [+-]?digits...
        if (
            ch in "+-"
            or ch.isdigit()
            or (ch == "." and pos + 1 < n and text[pos + 1].isdigit())
        ):
            end = pos
            # Greedy match of number-like characters
            while end < n and text[end] not in _ATOM_END:
                end += 1
            token = text[pos:end]
            if _RE_NUMBER.match(token):
                yield _Token(NUMBER, token, line)
            elif _RE_BARE.match(token):
                yield _Token(BARE, token, line)
            else:
                yield _Token(PLAIN, token, line)
            pos = end
            continue

        # Bare word
        end = pos
        while end < n and text[end] not in _ATOM_END:
            end += 1
        token = text[pos:end]
        kind = BARE if _RE_BARE.match(token) else PLAIN
        yield _Token(kind, token, line)
        pos = end

    yield _Token(END, None, line)


# ── parser ───────────────────────────────────────────────────────────────────
#
# Each function mirrors a rule from test/reference_parser/grammar.lark.
# Tokens are consumed from a shared _ParserState.


class _ParserState:
    """Mutable parse state: token stream + position."""

    __slots__ = ("tokens", "pos", "_saved")

    def __init__(self, tokens: list[_Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        self._saved: int = 0

    def peek(self) -> _Token:
        return self.tokens[self.pos]

    def next(self) -> _Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def peek_ahead(self, offset: int = 1) -> _Token:
        """Peek at token at pos+offset without advancing."""
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]  # END token
        return self.tokens[idx]

    def expect(self, kind: str) -> _Token:
        t = self.next()
        if t.kind != kind:
            if t.kind == END and kind == RPAREN:
                msg = (
                    "Unexpected end of input.\n\n"
                    "Expected one of the following:\n"
                    "  - a closing parenthesis `)`\n"
                )
            elif t.kind == END:
                msg = f"Unexpected end of input (expected {kind})"
            else:
                msg = f"Expected {kind}, found {t.kind} ({t.value!r})"
            raise _SxpbSyntaxError(msg, t.line)
        return t

    def at_end(self) -> bool:
        return self.peek().kind == END

    def save(self) -> None:
        self._saved = self.pos

    def restore(self) -> None:
        self.pos = self._saved

    def skip_newlines(self) -> None:
        """Skip blank lines between toplevel expressions."""
        while self.peek().kind == END:
            return  # actual end
        # END is the real sentinel; blank lines are just whitespace (already skipped)


# ── toplevel dispatch ────────────────────────────────────────────────────────

# start: message_body
#       | discriminated_array
#       | discriminated_dict
#       | discriminated_manyof
#       | discriminated_nest
#
# The parser detects which rule to use by looking at the first token.


def _parse_start(st: _ParserState) -> Any:
    t = st.peek()
    if t.kind == LIST_DISCRIM:
        # Could be discriminated_array or discriminated_manyof.
        # We peek past LIST_DISCRIM to decide.
        return _parse_discriminated_list(st)
    elif t.kind == DICT_DISCRIM:
        return _parse_discriminated_dict(st)
    elif t.kind == NEST_DISCRIM:
        return _parse_discriminated_nest(st)
    elif t.kind == END:
        raise _SxpbSyntaxError("Unexpected end of input", 0)
    elif t.kind == RPAREN:
        t = st.next()
        raise _SxpbSyntaxError(
            "Found an unexpected character ')'.\n\n"
            "Expected one of the following:\n"
            "  - an opening parenthesis `(`\n",
            t.line,
        )
    else:
        # Must be message_body — return as toplevel Mesg
        return SxpbMesg(_parse_message_body(st, allow_empty=True))


# ── discriminators ───────────────────────────────────────────────────────────

# discriminated_array: LIST_DISCRIM array_body
# discriminated_manyof: LIST_DISCRIM any_field manyof_item*
#
# These share a LIST_DISCRIM prefix.  We merge them into one parse function
# and disambiguate from the first element.


def _parse_discriminated_list(st: _ParserState, stop_kind: str = END) -> Any:
    """Parse LIST_DISCRIM ... as either discriminated_array or discriminated_manyof.

    stop_kind indicates which token stops the list:
    - END for toplevel (no closing paren)
    - RPAREN when the list is a field value
    """
    st.expect(LIST_DISCRIM)
    if st.peek().kind == END or st.peek().kind == RPAREN:
        return SxpbList()

    t = st.peek()
    if t.kind == DICT_DISCRIM:
        return _parse_array_body(st)
    elif t.kind in (NUMBER, BOOLEAN, QUOTED_STRING, MULTILINE_STRING):
        # Scalar array (numbers, booleans, or strings)
        return _parse_array_body(st)
    elif t.kind == STRING_DISCRIM:
        # discriminated string → string array
        return _parse_array_body(st)
    elif t.kind in (BARE, PLAIN):
        return _parse_array_body(st)
    elif t.kind == LPAREN:
        # Ambiguous: could be an array of messages or a manyof.
        # Parse with list-item disambiguation.
        return _parse_discriminated_list_content(st, stop_kind)
    else:
        raise _SxpbSyntaxError("Unexpected list element.", t.line)


class _ScalarListNormalizer:
    """Reconcile scalar elements using the first element's literal kind."""

    def __init__(self) -> None:
        self._kind: str | None = None

    @property
    def string_first(self) -> bool:
        return self._kind == "string"

    def normalize(
        self,
        value: Any,
        token: _Token,
        *,
        spelling: str | None = None,
    ) -> Any:
        if self._kind is None:
            if isinstance(value, str):
                self._kind = "string"
            elif isinstance(value, bool):
                self._kind = "bool"
            else:
                self._kind = "number"

        if self._kind == "string":
            return spelling if spelling is not None else value

        if self._kind == "number":
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
            raise _SxpbSyntaxError("Unexpected literal type.", token.line)

        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            if (
                spelling is not None
                and not spelling.startswith("-")
                and value in (0, 1)
            ):
                return bool(value)
            raise _SxpbSyntaxError("Expected a bool, not an int.", token.line)
        raise _SxpbSyntaxError("Unexpected literal type.", token.line)


class _AnonymousListNormalizer:
    """Apply array element-kind constraints to anonymous list elements."""

    def __init__(self, *, container: str) -> None:
        self._container = container
        self._kind: str | None = None
        self._scalar = _ScalarListNormalizer()

    @property
    def string_first(self) -> bool:
        return self._kind == "scalar" and self._scalar.string_first

    def normalize(
        self,
        value: Any,
        token: _Token,
        *,
        spelling: str | None = None,
    ) -> Any:
        is_message = isinstance(value, (SxpbMesg, SxpbDict))
        incoming_kind = "message" if is_message else "scalar"
        if self._kind is None:
            self._kind = incoming_kind
        elif self._kind != incoming_kind:
            if incoming_kind == "message":
                raise _SxpbSyntaxError(
                    f"Unexpected message {self._container} element.", token.line
                )
            raise _SxpbSyntaxError("Unexpected literal type.", token.line)

        if is_message:
            return value
        return self._scalar.normalize(value, token, spelling=spelling)


def _reject_reserved_array_string_starter(token: _Token) -> None:
    """Reject a PLAIN atom until a first string establishes string context."""
    raise _SxpbSyntaxError(
        f"A bare word cannot begin with a reserved prefix (got {token.value!r}).",
        token.line,
    )


def _parse_array_body(
    st: _ParserState, already_have_discriminators: bool = False
) -> SxpbList:
    """Parse an array, reconciling every element with its first element kind."""
    result = SxpbList()
    scalar_normalizer = _ScalarListNormalizer()
    array_kind: str | None = None

    def accept_message(token: _Token) -> None:
        nonlocal array_kind
        if array_kind == "scalar":
            raise _SxpbSyntaxError("Unexpected message array element.", token.line)
        array_kind = "message"

    def accept_scalar(token: _Token, *, spelling: str | None = None) -> None:
        nonlocal array_kind
        if array_kind == "message":
            raise _SxpbSyntaxError("Unexpected literal type.", token.line)
        array_kind = "scalar"
        result[-1] = scalar_normalizer.normalize(result[-1], token, spelling=spelling)

    while not st.at_end():
        t = st.peek()
        if t.kind == RPAREN:
            break
        if t.kind == END:
            break

        if t.kind == DICT_DISCRIM:
            accept_message(t)
            _parse_message_array_item(st, result)
        elif t.kind == LPAREN:
            # anonymous_discriminated_message or anonymous_discriminated_string
            _parse_message_array_item(st, result)
            if isinstance(result[-1], str):
                accept_scalar(t)
            else:
                accept_message(t)
        elif t.kind == STRING_DISCRIM:
            # Inside an array, bare ``""`` is one empty string element.
            # Parenthesized ``("" words...)`` remains discriminated and greedy.
            st.next()
            result.append("")
            accept_scalar(t)
        elif t.kind in (QUOTED_STRING, MULTILINE_STRING, BARE):
            _parse_string_array_item(st, result)
            accept_scalar(t)
        elif t.kind == PLAIN:
            if not scalar_normalizer.string_first:
                _reject_reserved_array_string_starter(t)
            _parse_string_array_item(st, result)
            accept_scalar(t)
        elif t.kind == NUMBER:
            spelling = t.value
            result.append(_number_from_spelling(spelling))
            accept_scalar(t, spelling=spelling)
            st.next()
        elif t.kind == BOOLEAN:
            spelling = t.value
            result.append(_boolean_from_spelling(spelling))
            accept_scalar(t, spelling=spelling)
            st.next()
        else:
            raise _SxpbSyntaxError("Unexpected list element.", t.line)

    return result


def _parse_message_array_item(st: _ParserState, result: SxpbList) -> None:
    """empty_message | anonymous_discriminated_message."""
    t = st.peek()
    if t.kind == DICT_DISCRIM:
        st.next()
        # empty_message: just a ()
        result.append(SxpbMesg())
    elif t.kind == LPAREN:
        st.next()
        t2 = st.peek()
        if t2.kind == DICT_DISCRIM:
            # anonymous_discriminated_message: ( () message_body )
            st.next()  # consume DICT_DISCRIM
            body = _parse_message_body(st, allow_empty=True)
            st.expect(RPAREN)
            result.append(body)
        elif t2.kind == STRING_DISCRIM:
            # anonymous_discriminated_string: ( "" ... )
            val = _parse_discriminated_string(st)
            st.expect(RPAREN)
            result.append(val)
        else:
            raise _SxpbSyntaxError(
                f'Expected () or ("") in array body, got {t2.kind}',
                t2.line,
            )


def _parse_string_array_item(st: _ParserState, result: SxpbList) -> None:
    """Parse one item of string_array_body."""
    t = st.peek()
    if t.kind == STRING_DISCRIM:
        st.next()
        val = _parse_string_body(st, discriminated=True)
        result.append(val)
    elif t.kind == LPAREN:
        # anonymous_discriminated_string: ( "" ... )
        st.next()
        st.expect(STRING_DISCRIM)
        val = _parse_string_body(st, discriminated=True)
        st.expect(RPAREN)
        result.append(val)
    elif t.kind in (QUOTED_STRING, MULTILINE_STRING):
        result.append(t.value)
        st.next()
    elif t.kind in (BARE, PLAIN):
        result.append(t.value)
        st.next()
    elif t.kind in (NUMBER, BOOLEAN):
        result.append(t.value)
        st.next()


def _parse_discriminated_list_content(st: _ParserState, stop_kind: str = END) -> Any:
    """Disambiguate discriminated_array vs discriminated_manyof by content.

    A named first element selects manyof; later anonymous elements do not
    change that choice.  stop_kind is END at top level and RPAREN in a field.
    """
    items: list[Any] = []
    scalar_normalizer = _ScalarListNormalizer()
    manyof_normalizer = _AnonymousListNormalizer(container="manyof")
    is_manyof = False
    array_kind: str | None = None

    while not st.at_end():
        t = st.peek()
        if t.kind == END:
            break
        if t.kind == RPAREN and stop_kind == RPAREN:
            break
        allow_plain = (
            manyof_normalizer.string_first
            if is_manyof
            else array_kind == "scalar" and scalar_normalizer.string_first
        )
        if t.kind == PLAIN and not allow_plain:
            _reject_reserved_array_string_starter(t)

        item = _parse_list_item(
            st,
            allow_plain=allow_plain,
            empty_string_item=bool(items) and not is_manyof,
        )
        if item is None:
            raise _SxpbSyntaxError("Unexpected list element.", t.line)

        is_named = isinstance(item, (tuple, SxpbLone, SxpbMany))
        is_anon_message = isinstance(item, (SxpbMesg, SxpbDict))
        if not items:
            is_manyof = is_named
        if is_manyof:
            if not is_named:
                spelling = t.value if t.kind in (NUMBER, BOOLEAN) else None
                item = manyof_normalizer.normalize(item, t, spelling=spelling)
            items.append(item)
            continue
        if is_named:
            raise _SxpbSyntaxError("Array cannot hold fields.", t.line)
        if is_anon_message:
            if array_kind == "scalar":
                raise _SxpbSyntaxError("Unexpected message array element.", t.line)
            array_kind = "message"
        else:
            if array_kind == "message":
                raise _SxpbSyntaxError("Unexpected literal type.", t.line)
            array_kind = "scalar"
            spelling = t.value if t.kind in (NUMBER, BOOLEAN) else None
            item = scalar_normalizer.normalize(item, t, spelling=spelling)
        items.append(item)

    if not items:
        return SxpbList()
    if not is_manyof:
        return SxpbList(items)

    return SxpbMany([_as_manyof_element(item) for item in items])


def _as_manyof_element(item: Any) -> Any:
    if isinstance(item, tuple):
        return SxpbLone({item[0]: item[1]})
    if isinstance(item, (SxpbLone, SxpbMany)):
        return item
    return SxpbLone({"": item})


def _parse_list_item(
    st: _ParserState,
    *,
    allow_plain: bool = False,
    empty_string_item: bool = False,
) -> Any:
    """Parse one list/manyof item with caller-selected string boundaries."""
    t = st.peek()
    if t.kind == NUMBER:
        st.next()
        return _number_from_spelling(t.value)
    if t.kind == BOOLEAN:
        st.next()
        return _boolean_from_spelling(t.value)
    if t.kind in (QUOTED_STRING, MULTILINE_STRING, BARE):
        st.next()
        return t.value
    if t.kind == PLAIN and allow_plain:
        st.next()
        return t.value
    if t.kind == STRING_DISCRIM:
        if empty_string_item:
            st.next()
            return ""
        # Outside an established array, this begins a discriminated string.
        return _parse_discriminated_string(st)
    if t.kind == LPAREN:
        st.next()
        inner = st.peek()
        if inner.kind == DICT_DISCRIM:
            # anonymous_discriminated_message: ( () message_body )
            st.next()
            body = _parse_message_body(st, allow_empty=True)
            st.expect(RPAREN)
            return body
        if inner.kind == STRING_DISCRIM:
            # anonymous_discriminated_string: ( "" ... )
            val = _parse_discriminated_string(st)
            st.expect(RPAREN)
            return val
        # any_field — _parse_any_field_content leaves pos at RPAREN.
        # We must consume it (unlike _parse_any_field which does).
        result = _parse_any_field_content(st)
        st.expect(RPAREN)
        return result
    if t.kind == DICT_DISCRIM:
        st.next()
        return SxpbMesg()
    return None


# ── discriminated_dict ───────────────────────────────────────────────────────

# discriminated_dict: DICT_DISCRIM message_body


def _parse_discriminated_dict(st: _ParserState) -> SxpbDict:
    st.expect(DICT_DISCRIM)
    return SxpbDict(_parse_message_body(st, allow_empty=True))


# ── discriminated_nest ───────────────────────────────────────────────────────

# discriminated_nest: NEST_DISCRIM nest_body


def _parse_discriminated_nest(st: _ParserState) -> SxpbNest:
    st.expect(NEST_DISCRIM)
    return _parse_nest_body(st)


# ── discriminated_string ─────────────────────────────────────────────────────

# discriminated_string: STRING_DISCRIM (ESCAPED_STRING | MULTILINE_STRING | PLAIN)*


def _parse_discriminated_string(st: _ParserState) -> str:
    st.expect(STRING_DISCRIM)
    return _parse_string_body(st, discriminated=True)


def _parse_string_body(st: _ParserState, discriminated: bool = False) -> str:
    """string_body: ( ESCAPED_STRING | MULTILINE_STRING | BARE )*
                 ( ESCAPED_STRING | MULTILINE_STRING | PLAIN )*

    In discriminated mode (after STRING_DISCRIM has been consumed),
    all tokens act like PLAIN and get spaces between them.
    """
    parts: list[str] = []
    prev_was_unquoted = False

    while not st.at_end():
        t = st.peek()
        if t.kind in (QUOTED_STRING, MULTILINE_STRING):
            parts.append(t.value)
            st.next()
            prev_was_unquoted = False
        elif t.kind in (BARE, PLAIN):
            if t.kind == PLAIN and not parts and not discriminated:
                break
            if prev_was_unquoted:
                parts.append(" ")
            parts.append(t.value)
            st.next()
            prev_was_unquoted = True
        elif t.kind == STRING_DISCRIM:
            st.next()
            prev_was_unquoted = False
        elif t.kind in (NUMBER, BOOLEAN):
            if prev_was_unquoted:
                parts.append(" ")
            parts.append(t.value)
            st.next()
            prev_was_unquoted = True
        else:
            break

    return "".join(parts)


# ── message_body ─────────────────────────────────────────────────────────────

# message_body: any_field*


def _parse_message_body(st: _ParserState, allow_empty: bool = False) -> SxpbMesg:
    """Parse any_field* and combine into a SxpbMesg."""
    msg = SxpbMesg()
    while not st.at_end():
        t = st.peek()
        if t.kind == RPAREN:
            break
        if t.kind == END:
            break
        if t.kind == LPAREN:
            field = _parse_any_field(st)
            if field is not None:
                key, value = field
                _merge_field_into_message(msg, key, value)
        elif t.kind == DICT_DISCRIM:
            # Empty field? Skip or treat as empty dict field
            st.next()
        else:
            raise _SxpbSyntaxError(
                f"Unexpected token outside field: {t.kind} ({t.value!r})",
                t.line,
            )

    return msg


def _merge_field_into_message(msg: SxpbDict | SxpbMesg, key: str, value: Any) -> None:
    """Add a field to a message, accumulating duplicate keys into SxpbLists."""
    if key in msg:
        existing = msg[key]
        if not isinstance(existing, UserList):
            msg[key] = SxpbList([existing])
        if isinstance(value, UserList):
            msg[key].extend(value)
        else:
            msg[key].append(value)
    else:
        msg[key] = value


# ── any_field ────────────────────────────────────────────────────────────────

# any_field: regular_field | loneof_field | manyof_field
#
# All start with LPAREN, but we disambiguate after consuming the first field_name.


def _parse_any_field(st: _ParserState) -> tuple[str, Any] | None:
    """Parse a complete field: LPAREN ... RPAREN → (key, value).

    ALWAYS consumes both LPAREN and RPAREN.
    """
    st.expect(LPAREN)
    result = _parse_any_field_content(st)
    st.expect(RPAREN)
    return result


def _parse_any_field_content(st: _ParserState) -> tuple[str, Any] | None:
    """Parse field content after LPAREN consumed; leaves position at RPAREN.

    IMPORTANT: does NOT consume the outer RPAREN.  Callers must do that.
    """
    t = st.peek()

    # After outer LPAREN, seeing LPAREN again means:
    #   loneof:   ((key subkey) value)
    #   manyof:   ((key) item1 item2 ...)
    if t.kind == LPAREN:
        st.next()  # consume inner LPAREN
        key = _parse_field_name(st)
        if st.peek().kind == RPAREN:
            # manyof short form: ((key) item*)
            st.next()  # consume RPAREN closing (key)
            items = _parse_manyof_items(st)
            # _parse_manyof_items stops at the field's closing RPAREN (unconsumed).
            if not items:
                return key, SxpbMany()
            return key, SxpbMany([_as_manyof_element(item) for item in items])
        else:
            # loneof: ((key subkey) value)
            subkey = _parse_field_name(st)
            st.expect(RPAREN)  # close (key subkey)
            value = _parse_field_value(st)
            return key, SxpbLone({subkey: value})

    # regular_field or manyof_field option 1: (field_name ...)
    key = _parse_field_name(st)

    if st.peek().kind == RPAREN:
        # (field_name) — empty value
        return key, SxpbMesg()

    if st.peek().kind == LIST_DISCRIM:
        # manyof_field option 1: (field_name LIST_DISCRIM any_field*)
        value = _parse_discriminated_list(st, stop_kind=RPAREN)
        return key, value

    # regular_field value
    value = _parse_field_value(st)
    return key, value


# ── field parsing helpers ────────────────────────────────────────────────────


def _parse_field_name(st: _ParserState) -> str:
    """field_name: BARE | NONEMPTY_ESCAPED_STRING."""
    t = st.next()
    if t.kind in (BARE, QUOTED_STRING):
        return str(t.value)
    if t.kind == STRING_DISCRIM:
        raise _SxpbSyntaxError("Found an unexpected character '\"'.", t.line)
    raise _SxpbSyntaxError(
        f"Expected field name, found {t.kind} ({t.value!r})",
        t.line,
    )


def _parse_field_value(st: _ParserState) -> Any:
    """Parse the value part of a field: scalar_body | message_body | discriminated_*.

    IMPORTANT: This function NEVER consumes the outer RPAREN of the enclosing
    field.  The caller (_parse_any_field_content) always does st.expect(RPAREN)
    after this returns.
    """
    t = st.peek()

    if t.kind == RPAREN:
        # message_body is allowed to be empty, including as a loneof value.
        return SxpbMesg()

    if t.kind == LPAREN:
        # Peek at token AFTER LPAREN to identify the value type without consuming.
        inner = st.peek_ahead(1)

        if inner.kind == LIST_DISCRIM:
            st.next()  # consume LPAREN, leaving LIST_DISCRIM for _parse_discriminated_list
            return _parse_discriminated_list(st, stop_kind=RPAREN)

        if inner.kind == DICT_DISCRIM:
            st.next()  # consume LPAREN
            st.next()  # consume DICT_DISCRIM
            # Parse message_body (fields), stop before outer RPAREN
            return SxpbDict(_parse_message_body(st, allow_empty=True))

        if inner.kind == NEST_DISCRIM:
            st.next()  # consume LPAREN, leaving NEST_DISCRIM
            return _parse_discriminated_nest(st)

        if inner.kind == RPAREN:
            st.next()  # consume LPAREN
            st.next()  # consume RPAREN → empty dict "()"
            return SxpbDict()

        if inner.kind == STRING_DISCRIM:
            st.next()  # consume LPAREN
            return _parse_discriminated_string(st)

        # Regular nested value: message_body (field* container).
        # Don't consume LPAREN — _parse_message_body calls _parse_any_field
        # which consumes the LPAREN and matching RPAREN.
        return _parse_message_body(st, allow_empty=True)

    if t.kind == NUMBER:
        st.next()
        return _number_from_spelling(t.value)

    if t.kind == BOOLEAN:
        st.next()
        return _boolean_from_spelling(t.value)

    if t.kind in (QUOTED_STRING, MULTILINE_STRING):
        return _parse_string_body(st)

    if t.kind == BARE:
        return _parse_string_body(st)

    if t.kind == STRING_DISCRIM:
        return _parse_discriminated_string(st)

    if t.kind == LIST_DISCRIM:
        return _parse_discriminated_list(st, stop_kind=RPAREN)

    if t.kind == DICT_DISCRIM:
        return _parse_discriminated_dict(st)

    if t.kind == NEST_DISCRIM:
        return _parse_discriminated_nest(st)

    raise _SxpbSyntaxError(
        f"Unexpected token in field value: {t.kind} ({t.value!r})",
        t.line,
    )


def _parse_manyof_items(st: _ParserState) -> list[Any]:
    """Parse a manyof body, ignoring named items during kind reconciliation."""
    items: list[Any] = []
    normalizer = _AnonymousListNormalizer(container="manyof")
    while not st.at_end():
        t = st.peek()
        if t.kind in (RPAREN, END):
            break
        if t.kind == PLAIN and not normalizer.string_first:
            _reject_reserved_array_string_starter(t)

        item = _parse_list_item(st, allow_plain=normalizer.string_first)
        if item is None:
            raise _SxpbSyntaxError("Unexpected manyof element.", t.line)
        if not isinstance(item, (tuple, SxpbLone, SxpbMany)):
            spelling = t.value if t.kind in (NUMBER, BOOLEAN) else None
            item = normalizer.normalize(item, t, spelling=spelling)
        items.append(item)
    return items


# ── nest ─────────────────────────────────────────────────────────────────────

# nest_body: nest_item*
# nest_item: nest_leaf | nest_subfield | discriminated_string_nest_subfield
#            | anonymous_discriminated_string | anonymous_discriminated_nest


def _parse_nest_body(st: _ParserState) -> SxpbNest:
    """Parse a nest body (already inside a nest, discriminator consumed)."""
    nest = SxpbNest()
    while not st.at_end():
        t = st.peek()
        if t.kind == RPAREN:
            break
        if t.kind == END:
            break
        item = _parse_nest_item(st)
        if item is None:
            raise _SxpbSyntaxError(
                "Nest can only hold nests and strings.",
                t.line,
            )
        nest.append(item)
    return nest


def _parse_subnest_name(st: _ParserState) -> str:
    """Parse a subnest name without scalar conversion."""
    t = st.next()
    if t.kind in (QUOTED_STRING, MULTILINE_STRING):
        return t.value
    if t.kind not in (BARE, PLAIN, NUMBER, BOOLEAN):
        raise _SxpbSyntaxError(
            f"Expected subnest name, found {t.kind} ({t.value!r})", t.line
        )

    if _has_sxpb_special_prefix(t.value):
        raise _SxpbSyntaxError(
            "Unexpected special prefix of plain subnest name.", t.line
        )
    return t.value


def _parse_nest_item(st: _ParserState) -> Any:
    """Parse a single nest item."""
    t = st.peek()

    if t.kind in (
        BARE,
        PLAIN,
        NUMBER,
        BOOLEAN,
        QUOTED_STRING,
        MULTILINE_STRING,
    ):
        # Every leaf token remains a string in nest context.
        st.next()
        return t.value

    if t.kind == LPAREN:
        st.next()
        inner = st.peek()

        if inner.kind == RPAREN:
            raise _SxpbSyntaxError("Unexpected empty parens in nest", inner.line)

        if inner.kind == STRING_DISCRIM:
            # Could be:
            #   - discriminated_string_nest_subfield: (subnest_name "")
            #   - anonymous_discriminated_string: ("" ...)
            #   - anonymous_discriminated_nest: ("" ("") ...)
            #   - nest_subfield with STRING_DISCRIM before nest body
            st.next()  # consume STRING_DISCRIM

            # What follows STRING_DISCRIM?
            after = st.peek()
            if after.kind == NEST_DISCRIM:
                # ("" ("") ...) → anonymous discriminated nest
                st.next()  # consume NEST_DISCRIM
                body = _parse_nest_body(st)
                st.expect(RPAREN)  # close inner paren
                return SxpbLone({"": body})  # wrap as lone for nest
            elif after.kind == RPAREN:
                # ("" ) — just an empty string discriminator
                st.next()  # consume RPAREN
                return ""
            else:
                # ( "" ... ) → anonymous discriminated string
                val = _parse_string_body(st, discriminated=True)
                st.expect(RPAREN)
                return val

        if inner.kind == NEST_DISCRIM:
            # anonymous_discriminated_nest: ( ("") nest_body )
            st.next()  # consume NEST_DISCRIM
            body = _parse_nest_body(st)
            st.expect(RPAREN)
            return SxpbLone({"": body})

        # Regular nest_subfield: ( subnest_name nest_body )
        # or: ( subnest_name NEST_DISCRIM nest_body )
        # or: ( subnest_name "" string_body )
        key = _parse_subnest_name(st)

        after_key = st.peek()
        if after_key.kind == RPAREN:
            # (key ) — empty nest subfield (key -> None)
            st.next()
            return SxpbLone({key: SxpbNest()})

        if after_key.kind == NEST_DISCRIM:
            # (key ("")) — explicit nest discriminator
            st.next()
            body = _parse_nest_body(st)
            st.expect(RPAREN)
            return SxpbLone({key: body})

        if after_key.kind == STRING_DISCRIM:
            # (key "" string_body) — discriminated string field
            st.next()
            val = _parse_string_body(st, discriminated=True)
            st.expect(RPAREN)
            return SxpbLone({key: SxpbNest([val])})

        if after_key.kind == LPAREN:
            # (key (sub_stuff ...)) — nested nest or subfield
            body = _parse_nest_body(st)
            st.expect(RPAREN)
            if len(body) == 1 and isinstance(body[0], str):
                return SxpbLone({key: SxpbNest([body[0]])})
            return SxpbLone({key: body})

        # (key ...) — parse the rest as a nest_body (items until RPAREN)
        body = _parse_nest_body(st)
        st.expect(RPAREN)
        return SxpbLone({key: body})

    if t.kind == STRING_DISCRIM:
        # Anonymous discriminated string at nest top level
        return _parse_discriminated_string(st)

    if t.kind == NEST_DISCRIM:
        # Anonymous nest: ("") nest_body
        st.next()
        return _parse_nest_body(st)

    return None


# ── public API ───────────────────────────────────────────────────────────────


def loads(text: str, precise: bool = False) -> Json:
    """Parse an SxPB string into Python objects.

    Handles multi-expression files (blank-line-separated toplevel expressions).
    The first expression is conventionally ``(())`` (a header line).
    Returns a dict if precise=False (converting to plain types),
    or the raw SxPB types if precise=True.
    """
    tokens = list(_tokenize(text))
    st = _ParserState(tokens)

    # Parse toplevel expressions (multi-expr files: first is usually (()) header)
    exprs: list[Any] = []
    while not st.at_end():
        expr = _parse_start(st)
        if expr is not None:
            exprs.append(expr)

    if not exprs:
        data: Any = SxpbMesg()
        return cast(Json, data if precise else to_plain_types(data))

    if len(exprs) == 1:
        data = exprs[0]
    else:
        data = exprs[0]
        for e in exprs:
            if isinstance(e, (SxpbDict, SxpbMesg)) and len(e) == 0:
                continue
            if isinstance(e, SxpbList) and len(e) == 0:
                continue
            data = e
            break

    if not precise:
        return to_plain_types(data)
    return data


def load(path: str, precise: bool = False) -> Json:
    """Parse an SxPB file."""
    with open(path, "r", encoding="utf-8") as f:
        return loads(f.read(), precise=precise)
