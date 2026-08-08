from collections import UserDict, UserList
from pathlib import Path

import pytest
from reference_parser import lark_parser

from sxpb import SxpbParseError
from sxpb import parse as hand_parse

CONTENT_DIR = Path(__file__).parent / "content"

VALID_SOURCES = [
    "",
    "(a 1) (b +true)",
    "() (a 1)",
    "( ) (a 1)",
    "(( )) 1 2",
    "( ( ) ) 1 2",
    '("") a (b c)',
    '( "" ) a (b c)',
    '(a "x\\n\\u263a")',
    '(a"adjacent quoted value")',
    '(a "" one two)',
    "(a (()) 1 2)",
    "(a (()) 1. word +true)",
    "(a (()) word 1. +true)",
    "(a ( ( ) ) 1 2)",
    "((kind option) (x 1))",
    "((event words_chosen))",
    "((history) ((event words_chosen)))",
    "(table ((phase_as flip) (player p2)) (status PLAYING))",
    "((kind) 1 two +false)",
    "((choice) (() (a 1)) ())",
    "(()) (a 1) 2 3",
    '(()) (a one) "2" "3"',
    "; comment\n(a 1)",
    '(value """first\nsecond""")',
    '("")\n(lens "" 50mm macro)',
    # Every has_sxpb_bare_prefix() branch: lone/doubled punctuation,
    # punctuation-prefixed words, and ordinary bare starters.
    "(dash -) (dot .)",
    "(- dash) (. dot)",
    "(double_dash --+) (double_dot ..-)",
    "(-word dash) (.word dot) (/ slash)",
    *[path.read_text() for path in sorted(CONTENT_DIR.glob("*.sxpb"))],
]

INVALID_SOURCES = [
    "(missing right parenthesis",
    "(extra right parenthesis))",
    '("" value)',
    '(my_nest ("") (my_string "" (illegal)))',
    '("") (x (()) y)',
    '("") (glasses (()) (() (material (()) brass)))',
    '(value "unterminated)',
    '(value """unterminated)',
    r'(value "unknown \q escape")',
    "(value +trueish)",
    "(value +almost)",
    # Non-bare special prefixes and numeric-looking field names.
    "(value +)",
    "(value -.)",
    "(value -+)",
    "(value .-)",
    "(value .+)",
    "(-1 value)",
    "(.1 value)",
    "(-1word value)",
]


def _type_snapshot(value):
    """Preserve precise SxPB containers and scalar types during comparison."""
    if isinstance(value, UserDict):
        return (
            type(value).__name__,
            tuple((key, _type_snapshot(item)) for key, item in value.items()),
        )
    if isinstance(value, UserList):
        return (type(value).__name__, tuple(_type_snapshot(item) for item in value))
    if isinstance(value, dict):
        return (
            "dict",
            tuple((key, _type_snapshot(item)) for key, item in value.items()),
        )
    if isinstance(value, list):
        return ("list", tuple(_type_snapshot(item) for item in value))
    return (type(value).__name__, value)


@pytest.mark.parametrize("source", VALID_SOURCES)
@pytest.mark.parametrize("precise", [False, True])
def test_parsers_agree_on_valid_sources(source, precise):
    grammar_result = lark_parser.loads(source, precise=precise)
    hand_result = hand_parse.loads(source, precise=precise)

    assert _type_snapshot(hand_result) == _type_snapshot(grammar_result)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("((choice) 1 (value 2))", {"choice": [{"": 1}, {"value": 2}]}),
        ("((choice) (() (a 1)) ())", {"choice": [{"": {"a": 1}}, {"": {}}]}),
        ("(()) (a 1) 2 3", [{"a": 1}, {"": 2}, {"": 3}]),
    ],
)
@pytest.mark.parametrize(
    "parse_module", [lark_parser, hand_parse], ids=["lark", "hand"]
)
def test_manyof_element_names_are_preserved(parse_module, source, expected):
    assert parse_module.loads(source, precise=True) == expected


@pytest.mark.parametrize(
    "parse_module", [lark_parser, hand_parse], ids=["lark", "hand"]
)
def test_plain_manyof_elements_use_value_name(parse_module):
    source = "((choice) 1 (value 2))"
    expected = {"choice": [{"value": 1}, {"value": 2}]}
    assert parse_module.loads(source) == expected


@pytest.mark.parametrize("source", INVALID_SOURCES)
@pytest.mark.parametrize(
    "parse_module", [lark_parser, hand_parse], ids=["lark", "hand"]
)
def test_parsers_reject_invalid_sources(source, parse_module):
    with pytest.raises(SxpbParseError):
        parse_module.loads(source, precise=True)
