import re
from typing import Iterator, Tuple

TOKEN_RE = re.compile(
    r'(?P<LPAR>\()|(?P<RPAR>\))|(?P<TDQUOTE>""")|(?P<DQUOTE>")|(?P<SEMICOLON>;[^\n]*)|(?P<WS>[\s]+)|(?P<ATOM>[^()\s";]+)',
    re.VERBOSE | re.DOTALL,
)


def tokenize(text: str) -> Iterator[Tuple[str, str]]:
    pos = 0
    L = len(text)
    while pos < L:
        m = TOKEN_RE.match(text, pos)
        if not m:
            yield ("ATOM", text[pos])
            pos += 1
            continue
        kind = m.lastgroup
        val = m.group()
        pos = m.end()
        if kind in ("WS", "SEMICOLON"):
            yield ("BLANK", val)
            continue
        if kind == "TDQUOTE":
            start = pos
            idx = text.find('"""', start)
            while idx != -1 and text[idx - 1 : idx] == "\\\\":
                idx = text.find('"""', idx + 3)
            if idx == -1:
                raise SyntaxError("Unterminated triple-quoted string")
            content = text[start:idx]
            pos = idx + 3
            yield ("STRING", content)
            continue
        if kind == "DQUOTE":
            buf = []
            i = pos
            escaped = False
            while i < L:
                ch = text[i]
                if escaped:
                    buf.append(ch)
                    escaped = False
                else:
                    if ch == "\\\\":
                        escaped = True
                    elif ch == '"':
                        break
                    else:
                        buf.append(ch)
                i += 1
            if i >= L or text[i] != '"':
                raise SyntaxError("Unterminated quoted string")
            content = "".join(buf)
            pos = i + 1
            yield ("STRING", content)
            continue
        if kind in ("LPAR", "RPAR", "ATOM"):
            yield (kind, val)
            continue
        yield (kind, val)
