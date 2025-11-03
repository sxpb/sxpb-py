import pytest
from lark import Lark
from pathlib import Path
from textwrap import dedent


@pytest.fixture
def sxpb_parser():
    grammar = (Path(__file__).parent / "prototype_grammar.lark").read_text()
    return Lark(grammar, start="start")


def test_simple_field(sxpb_parser):
    sxpb_parser.parse('(key "value")')


def test_simple_message(sxpb_parser):
    sxpb_parser.parse('(key (field "value"))')


def test_nested_message_and_array(sxpb_parser):
    s = dedent("""
        (languages (())
         (()
          (name "Python (PEP 8)")
          (spaces 4)
         )
        )
    """)
    sxpb_parser.parse(s)


def test_named_message(sxpb_parser):
    sxpb_parser.parse('(message (name "value"))')


def test_array_of_scalars(sxpb_parser):
    sxpb_parser.parse('(items (()) "a" "b" "c")')


def test_array_of_messages(sxpb_parser):
    s = dedent("""
        (items (())
         (() (name "a"))
         (() (name "b"))
         (() (name "c"))
        )
    """)
    sxpb_parser.parse(s)


def test_parse_message_sxpb(sxpb_parser):
    content = (Path(__file__).parent / "content" / "message.sxpb").read_text()
    sxpb_parser.parse(content)


def test_parse_array_sxpb(sxpb_parser):
    content = (Path(__file__).parent / "content" / "array.sxpb").read_text()
    sxpb_parser.parse(content)


def test_parse_string_sxpb(sxpb_parser):
    content = (Path(__file__).parent / "content" / "string.sxpb").read_text()
    sxpb_parser.parse(content)


def test_parse_loneof_sxpb(sxpb_parser):
    content = (Path(__file__).parent / "content" / "loneof.sxpb").read_text()
    sxpb_parser.parse(content)


def test_parse_manyof_sxpb(sxpb_parser):
    content = (Path(__file__).parent / "content" / "manyof.sxpb").read_text()
    sxpb_parser.parse(content)


def test_toplevel_array_of_scalars(sxpb_parser):
    sxpb_parser.parse('(()) "a" "b" "c"')


def test_toplevel_array_of_messages(sxpb_parser):
    s = dedent("""
        (())
        (() (name "a"))
        (() (name "b"))
        (() (name "c"))
    """)
    sxpb_parser.parse(s)


def test_toplevel_empty_array(sxpb_parser):
    sxpb_parser.parse("(())")


def test_simple_manyof(sxpb_parser):
    s = dedent("""
        (items (())
         (item (name "a"))
         (item (name "b"))
        )
    """)
    sxpb_parser.parse(s)


def test_toplevel_manyof(sxpb_parser):
    s = dedent("""
        (())
        (item (name "a"))
        (item (name "b"))
    """)
    sxpb_parser.parse(s)


def test_array_with_unquoted_strings(sxpb_parser):
    s = dedent("""
        (my_array (())
         ("" this is a "multi-word" string)
         ("" so is this)
         these
         are
         not
        )
    """)
    sxpb_parser.parse(s)
