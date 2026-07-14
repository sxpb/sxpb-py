"""Source-preserving formatting for SxPB files."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


class SxpbFormatError(ValueError):
    """Raised when source cannot be safely formatted."""


@dataclass
class _Token:
    kind: str
    text: str
    offset: int


_NEWLINE_RE = re.compile(r"\r\n|\r|\n")
_HORIZONTAL_WHITESPACE = " \t\v\f"


def _location(text: str, offset: int) -> str:
    line = text.count("\n", 0, offset) + 1
    last_newline = text.rfind("\n", 0, offset)
    column = offset + 1 if last_newline < 0 else offset - last_newline
    return f"line {line}, column {column}"


def _raise_at(text: str, offset: int, message: str) -> None:
    raise SxpbFormatError(f"{message} at {_location(text, offset)}")


def _find_multiline_end(text: str, start: int) -> int:
    search_from = start + 3
    while True:
        end = text.find('"""', search_from)
        if end < 0:
            _raise_at(text, start, "Unterminated triple-quoted string")

        backslashes = 0
        i = end - 1
        while i >= 0 and text[i] == "\\":
            backslashes += 1
            i -= 1
        if backslashes % 2 == 0:
            return end + 3
        search_from = end + 3


def _find_string_end(text: str, start: int) -> int:
    i = start + 1
    escaped = False
    while i < len(text):
        char = text[i]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            return i + 1
        i += 1
    _raise_at(text, start, "Unterminated quoted string")
    raise AssertionError("unreachable")


def _tokenize(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    i = 0
    while i < len(text):
        start = i
        char = text[i]
        if text.startswith('"""', i):
            i = _find_multiline_end(text, i)
            tokens.append(_Token("MULTILINE_STRING", text[start:i], start))
        elif char == '"':
            i = _find_string_end(text, i)
            tokens.append(_Token("STRING", text[start:i], start))
        elif char == ";":
            newline = text.find("\n", i)
            i = len(text) if newline < 0 else newline
            tokens.append(_Token("COMMENT", text[start:i], start))
        elif char == "(":
            i += 1
            tokens.append(_Token("LPAR", char, start))
        elif char == ")":
            i += 1
            tokens.append(_Token("RPAR", char, start))
        elif char.isspace():
            i += 1
            while i < len(text) and text[i].isspace():
                i += 1
            tokens.append(_Token("WS", text[start:i], start))
        else:
            i += 1
            while i < len(text):
                char = text[i]
                if char.isspace() or char in '();"':
                    break
                i += 1
            tokens.append(_Token("ATOM", text[start:i], start))
    return tokens


def _validate_structure(text: str, tokens: Iterable[_Token]) -> None:
    openings: list[_Token] = []
    for token in tokens:
        if token.kind == "LPAR":
            openings.append(token)
        elif token.kind == "RPAR":
            if not openings:
                _raise_at(text, token.offset, "Unexpected closing parenthesis")
            openings.pop()

    if openings:
        _raise_at(text, openings[-1].offset, "Unclosed opening parenthesis")


def _move_first_item_before_comments(tokens: list[_Token]) -> None:
    i = 0
    while i < len(tokens):
        if tokens[i].kind != "LPAR":
            i += 1
            continue

        j = i + 1
        saw_comment = False
        while j < len(tokens) and tokens[j].kind in {"WS", "COMMENT"}:
            saw_comment = saw_comment or tokens[j].kind == "COMMENT"
            j += 1
        if saw_comment and j < len(tokens):
            first_item = tokens.pop(j)
            following_starts_line = (
                j < len(tokens)
                and tokens[j].kind == "WS"
                and _NEWLINE_RE.search(tokens[j].text)
            )
            if following_starts_line and j - 1 > i and tokens[j - 1].kind == "WS":
                del tokens[j - 1]
            tokens.insert(i + 1, first_item)
        i += 1


def _remove_whitespace_after_open(tokens: list[_Token]) -> None:
    for i, token in enumerate(tokens[:-1]):
        if token.kind == "LPAR" and tokens[i + 1].kind == "WS":
            tokens[i + 1].text = ""


def _canonicalize_multiline_quoted_strings(tokens: list[_Token]) -> None:
    for token in tokens:
        if token.kind != "STRING":
            continue
        content = token.text[1:-1]
        newline = _NEWLINE_RE.search(content)
        if newline is None:
            continue
        token.kind = "MULTILINE_STRING"
        token.text = f'"""\\{newline.group(0)}{content}"""'


def _non_whitespace_signature(
    tokens: list[_Token], start: int, count: int
) -> tuple[list[str], list[int]]:
    kinds: list[str] = []
    indexes: list[int] = []
    i = start
    while i < len(tokens) and len(kinds) < count:
        if tokens[i].kind == "COMMENT":
            break
        if tokens[i].kind != "WS":
            kinds.append(tokens[i].kind)
            indexes.append(i)
        i += 1
    return kinds, indexes


def _discriminator_indexes(tokens: list[_Token], start: int) -> list[int]:
    token = tokens[start]
    if token.kind == "STRING" and token.text == '""':
        return [start]
    if token.kind != "LPAR":
        return []

    kinds, indexes = _non_whitespace_signature(tokens, start, 4)
    if kinds[:2] == ["LPAR", "RPAR"]:
        return indexes[:2]
    if kinds[:4] == ["LPAR", "LPAR", "RPAR", "RPAR"]:
        return indexes[:4]
    if kinds[:3] == ["LPAR", "STRING", "RPAR"] and tokens[indexes[1]].text == '""':
        return indexes[:3]
    return []


def _join_field_discriminators(tokens: list[_Token]) -> None:
    i = 0
    while i < len(tokens):
        if tokens[i].kind != "LPAR" or i + 2 >= len(tokens):
            i += 1
            continue

        head = tokens[i + 1]
        if head.kind not in {"ATOM", "STRING"}:
            i += 1
            continue

        discriminator_start = i + 2
        while discriminator_start < len(tokens) and tokens[
            discriminator_start
        ].kind in {"WS", "COMMENT"}:
            discriminator_start += 1
        if discriminator_start >= len(tokens):
            i += 1
            continue

        discriminator = _discriminator_indexes(tokens, discriminator_start)
        if not discriminator:
            i += 1
            continue

        trivia = tokens[i + 2 : discriminator_start]
        has_comment = any(token.kind == "COMMENT" for token in trivia)
        has_newline = any(
            token.kind == "WS" and _NEWLINE_RE.search(token.text) for token in trivia
        )
        if not has_comment and not has_newline:
            i += 1
            continue

        kept_trivia = trivia
        if has_comment and kept_trivia and kept_trivia[-1].kind == "WS":
            kept_trivia = kept_trivia[:-1]
        elif not has_comment:
            kept_trivia = []

        last = discriminator[-1]
        compact_discriminator = [
            token
            for token in tokens[discriminator_start : last + 1]
            if token.kind != "WS"
        ]
        replacement = [
            _Token("WS", " ", head.offset),
            *compact_discriminator,
            *kept_trivia,
        ]
        tokens[i + 2 : last + 1] = replacement
        i += 1


def _coalesce_whitespace(tokens: list[_Token]) -> None:
    i = 1
    while i < len(tokens):
        if tokens[i - 1].kind == "WS" and tokens[i].kind == "WS":
            tokens[i - 1].text += tokens[i].text
            del tokens[i]
        else:
            i += 1


def _leading_close_count(tokens: list[_Token], start: int) -> int:
    count = 0
    i = start
    while i < len(tokens):
        token = tokens[i]
        if token.kind == "RPAR":
            count += 1
        elif token.kind == "WS" and not _NEWLINE_RE.search(token.text):
            pass
        else:
            break
        i += 1
    return count


def _replace_line_indent(whitespace: str, indent: int) -> str:
    matches = list(_NEWLINE_RE.finditer(whitespace))
    if not matches:
        return " " * indent
    return whitespace[: matches[-1].end()] + " " * indent


def _normalize_indentation(tokens: list[_Token]) -> None:
    depth = 0
    at_start = True

    for i, token in enumerate(tokens):
        if token.kind == "WS":
            has_newline = _NEWLINE_RE.search(token.text) is not None
            if has_newline or at_start:
                next_index = i + 1
                closes = _leading_close_count(tokens, next_index)
                expected = max(0, depth - closes)
                token.text = _replace_line_indent(token.text, expected)
                at_start = True
            continue

        if token.kind == "LPAR":
            depth += 1
        elif token.kind == "RPAR":
            depth -= 1

        at_start = token.text.endswith(("\n", "\r"))


def _space_same_line_comments(tokens: list[_Token]) -> None:
    line_has_content = False
    previous_text = ""

    for token in tokens:
        if token.kind == "WS":
            if _NEWLINE_RE.search(token.text):
                line_has_content = False
            previous_text = token.text
            continue

        if token.kind == "COMMENT":
            if (
                line_has_content
                and previous_text
                and previous_text[-1] not in _HORIZONTAL_WHITESPACE
            ):
                token.text = " " + token.text
            previous_text = token.text
            continue

        if _NEWLINE_RE.search(token.text):
            final_newline = list(_NEWLINE_RE.finditer(token.text))[-1]
            line_has_content = bool(token.text[final_newline.end() :])
        else:
            line_has_content = True
        previous_text = token.text


def format_sxpb(text: str) -> str:
    """Format SxPB source while preserving comments and data spelling."""

    tokens = _tokenize(text)
    _validate_structure(text, tokens)
    _move_first_item_before_comments(tokens)
    _remove_whitespace_after_open(tokens)
    _canonicalize_multiline_quoted_strings(tokens)
    _join_field_discriminators(tokens)
    _coalesce_whitespace(tokens)
    _normalize_indentation(tokens)
    _space_same_line_comments(tokens)
    return "".join(token.text for token in tokens)
