"""U+FEFF is content, not SxPB whitespace.

Callers that choose to support a UTF-8 BOM must remove it while decoding.
The parser must not silently discard an already-decoded character.
"""

import pytest

from sxpb import SxpbParseError
from sxpb.parse import loads


def test_leading_bom_is_rejected():
    with pytest.raises(SxpbParseError):
        loads("\ufeff(a 1)")
    with pytest.raises(SxpbParseError):
        loads("\ufeff(a 1)", precise=True)


def test_repeated_leading_bom_is_rejected():
    with pytest.raises(SxpbParseError):
        loads("\ufeff\ufeff(a 1)")


def test_mid_document_bom_is_rejected():
    with pytest.raises(SxpbParseError):
        loads("(a 1)\ufeff(b 2)")


def test_standalone_bom_in_value_position_is_content():
    assert loads("(a \ufeff 1)") == {"a": "\ufeff 1"}


def test_bom_inside_bare_atom_is_content():
    assert loads("(a x\ufeffy)") == {"a": "x\ufeffy"}


def test_bom_inside_quoted_string_is_content():
    assert loads('(a "\ufeff")') == {"a": "\ufeff"}


def test_cli_rejects_leading_bom(run_sxpb2sxpb_tool):
    result = run_sxpb2sxpb_tool([], stdin_data="\ufeff(bom 1)")
    assert result.returncode == 1
    assert "Validation failed:" in result.stderr
