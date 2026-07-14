from pathlib import Path

import pytest

import sxpb
from sxpb.formatter import SxpbFormatError, format_sxpb


CONTENT_DIR = Path(__file__).parent / "content"


def test_one_space_indentation_and_grouped_closings():
    source = """  (a
      ( b
       (c
          (d stuff)
       ))
      ; just did not feel like triple closing
       )
"""
    expected = """(a
 (b
  (c
   (d stuff)
 ))
 ; just did not feel like triple closing
)
"""

    assert format_sxpb(source) == expected


def test_triple_grouped_closing_has_no_indent():
    source = """(a
 (b
  (c
     (d value)
   )))
"""
    expected = """(a
 (b
  (c
   (d value)
)))
"""

    assert format_sxpb(source) == expected


def test_open_parenthesis_has_content_on_same_line_without_space():
    source = """(
  ()
  ( name value)
)
"""
    expected = """(()
 (name value)
)
"""

    assert format_sxpb(source) == expected


@pytest.mark.parametrize("discriminator", ["()", "(())", '("")', '""'])
def test_field_discriminator_is_joined_to_field_name(discriminator):
    source = f"""(field
  {discriminator}
  value
)
"""
    expected = f"""(field {discriminator}
 value
)
"""

    assert format_sxpb(source) == expected


def test_discriminator_internal_whitespace_is_compacted_when_joined():
    source = """(field
  ( ( ) )
  value
)
"""

    assert (
        format_sxpb(source)
        == """(field (())
 value
)
"""
    )


def test_comment_before_first_item_moves_after_it():
    source = """(
 ; describes the anonymous message
 ()
 (value yes)
)
"""
    expected = """(()
 ; describes the anonymous message
 (value yes)
)
"""

    assert format_sxpb(source) == expected


def test_comment_between_field_and_discriminator_moves_after_discriminator():
    source = """(field
 ; describes the array
 (())
 one
 two
)
"""
    expected = """(field (())
 ; describes the array
 one
 two
)
"""

    assert format_sxpb(source) == expected


def test_same_line_comment_gets_at_least_one_space():
    source = """(a one); inserted
(b two) ; preserved
(c three)  ; customary gutter
(d four)       ; aligned
; comment only
"""
    expected = """(a one) ; inserted
(b two) ; preserved
(c three)  ; customary gutter
(d four)       ; aligned
; comment only
"""

    assert format_sxpb(source) == expected


def test_semicolons_and_parentheses_inside_strings_are_opaque():
    source = '''(value "(not; syntax)")
(plain_multiline "first
 (content); remains
   exactly indented
last")
(multiline """\\
 (content); remains
   exactly indented
""")
(after yes); comment
'''
    expected = '''(value "(not; syntax)")
(plain_multiline """\\
first
 (content); remains
   exactly indented
last""")
(multiline """\\
 (content); remains
   exactly indented
""")
(after yes) ; comment
'''

    assert format_sxpb(source) == expected


@pytest.mark.parametrize(
    ("content", "decoded"),
    [
        ("first\nsecond", "first\nsecond"),
        ("\nleading newline", "\nleading newline"),
        ("trailing newline\n", "trailing newline\n"),
        ("first\r\nsecond\r\n", "first\nsecond\n"),
        (
            'escaped \\"quote\\" and \\\\ backslash\nlast',
            'escaped "quote" and \\ backslash\nlast',
        ),
        (
            "  leading spaces\n    deeper indentation",
            "  leading spaces\n    deeper indentation",
        ),
    ],
)
def test_physical_newlines_in_quoted_strings_become_true_multiline_strings(
    content, decoded
):
    source = f'(value "{content}")\n'

    formatted = format_sxpb(source)

    newline = "\r\n" if "\r\n" in content else "\n"
    assert formatted.startswith(f'(value """\\{newline}')
    assert formatted.endswith('""")\n')
    assert sxpb.loads(source, precise=True) == {"value": decoded}
    assert sxpb.loads(formatted, precise=True) == sxpb.loads(source, precise=True)
    assert format_sxpb(formatted) == formatted


def test_escaped_newline_stays_in_ordinary_quoted_string():
    source = r'(value "first\nsecond")' + "\n"

    assert format_sxpb(source) == source
    assert sxpb.loads(source, precise=True) == {"value": "first\nsecond"}


def test_formatting_is_idempotent():
    source = """ (a
   ( b ( ( ) )
      (c d); note
   ))
"""

    once = format_sxpb(source)
    assert format_sxpb(once) == once


@pytest.mark.parametrize(
    "source, message",
    [
        ("(a", "Unclosed opening parenthesis"),
        ("(a))", "Unexpected closing parenthesis"),
        ('(a "unterminated)', "Unterminated quoted string"),
        ('(a """unterminated)', "Unterminated triple-quoted string"),
    ],
)
def test_malformed_or_ambiguous_source_is_rejected(source, message):
    with pytest.raises(SxpbFormatError, match=message):
        format_sxpb(source)


@pytest.mark.parametrize("path", sorted(CONTENT_DIR.glob("*.sxpb")))
def test_existing_fixture_remains_semantically_equivalent(path):
    source = path.read_text()
    formatted = format_sxpb(source)

    assert sxpb.loads(formatted, precise=True) == sxpb.loads(source, precise=True)
    assert format_sxpb(formatted) == formatted
