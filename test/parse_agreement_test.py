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
    "(a 1e6)",
    "(a 1e+6)",
    "(a +1e6)",
    "(a 1E3)",
    "(a (()) one 02 +03 4.0 +true)",
    "(a (()) 1 2.5 3)",
    "(a (()) +true 00 +01 +false)",
    '(a (()) "" one 02 +true)',
    "(()) one 02 +true",
    '(()) ("" one) 2 +true',
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
    "(a (()) word 1. +true)",
    "(a ( ( ) ) 1 2)",
    "((kind option) (x 1))",
    "((event words_chosen))",
    "((history) ((event words_chosen)))",
    "(table ((phase_as flip) (player p2)) (status PLAYING))",
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
    "((kind) 1 two +false)",
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
    "name",
    [
        "name",
        "-",
        ".",
        "--",
        "..",
        "---",
        "...",
        "--+",
        "..-",
        "-name",
        ".name",
        "1",
        "01",
        "1.2",
        ".5",
        "-1",
        "-0.5",
        "-1e6",
        "01.2300",
        "1e9999",
        "9007199254740993",
        "-0.000000000000000000000000001",
    ],
)
@pytest.mark.parametrize(
    "parse_module", [lark_parser, hand_parse], ids=["lark", "hand"]
)
def test_plain_subnest_names_match_fildesh_special_prefix_rule(parse_module, name):
    source = f'(nest ("") ({name} leaf))'
    assert parse_module.loads(source) == {"nest": [{name: ["leaf"]}]}


@pytest.mark.parametrize(
    ("spelling", "name"),
    [
        ('"+name"', "+name"),
        ('"-.name"', "-.name"),
        ('""".+name"""', ".+name"),
    ],
)
@pytest.mark.parametrize(
    "parse_module", [lark_parser, hand_parse], ids=["lark", "hand"]
)
def test_quoted_subnest_names_bypass_special_prefix_rule(parse_module, spelling, name):
    source = f'(nest ("") ({spelling} leaf))'
    assert parse_module.loads(source) == {"nest": [{name: ["leaf"]}]}


@pytest.mark.parametrize(
    "spelling",
    [
        "+",
        "+name",
        "+1",
        "+true",
        "-+",
        "-+name",
        "-.",
        "-.5",
        ".+",
        ".+name",
        ".-",
        ".-name",
    ],
)
@pytest.mark.parametrize(
    "parse_module", [lark_parser, hand_parse], ids=["lark", "hand"]
)
def test_plain_subnest_names_reject_fildesh_special_prefixes(parse_module, spelling):
    with pytest.raises(SxpbParseError):
        parse_module.loads(f'(nest ("") ({spelling} leaf))')


@pytest.mark.parametrize(
    "parse_module", [lark_parser, hand_parse], ids=["lark", "hand"]
)
def test_special_prefixes_remain_valid_nest_leaf_strings(parse_module):
    source = '(nest ("") +true +false +1 -.5 +name (child +value -.value))'
    assert parse_module.loads(source) == {
        "nest": [
            "+true",
            "+false",
            "+1",
            "-.5",
            "+name",
            {"child": ["+value", "-.value"]},
        ]
    }


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "(a (()) one 02 +03 4.0 +true)",
            {"a": ["one", "02", "+03", "4.0", "+true"]},
        ),
        ('(a (()) "one" 2 +true)', {"a": ["one", "2", "+true"]}),
        ('(a (()) ("" one) 2 +true)', {"a": ["one", "2", "+true"]}),
        ('(a (()) "" one 02 +true)', {"a": ["", "one", "02", "+true"]}),
        ("(()) one 02 +true", ["one", "02", "+true"]),
        ('(()) ("" one) 2 +true', ["one", "2", "+true"]),
        ("(a (()) 1 2.5 3)", {"a": [1, 2.5, 3]}),
        (
            "(a (()) +true 00 +01 +false)",
            {"a": [True, False, True, False]},
        ),
    ],
)
@pytest.mark.parametrize(
    "parse_module", [lark_parser, hand_parse], ids=["lark", "hand"]
)
def test_first_scalar_controls_array_string_conversion(parse_module, source, expected):
    assert _type_snapshot(parse_module.loads(source)) == _type_snapshot(expected)


@pytest.mark.parametrize(
    "source",
    [
        "(a (()) +truex)",
        "(a (()) -.x)",
        "(a (()) 1x)",
        "(a (()) 1 +truex)",
        "(a (()) 1 1x)",
        "(a (()) 1 one +truex)",
    ],
)
@pytest.mark.parametrize(
    "parse_module", [lark_parser, hand_parse], ids=["lark", "hand"]
)
def test_reserved_prefix_array_strings_require_string_first_context(
    parse_module, source
):
    with pytest.raises(SxpbParseError):
        parse_module.loads(source)


@pytest.mark.parametrize(
    "parse_module", [lark_parser, hand_parse], ids=["lark", "hand"]
)
def test_string_first_array_allows_reserved_prefix_continuations(parse_module):
    source = "(a (()) one +truex -.x)"
    assert parse_module.loads(source) == {"a": ["one", "+truex", "-.x"]}


@pytest.mark.parametrize(
    "source",
    [
        '(a (()) 1 "word")',
        "(a (()) 1 word)",
        '(a (()) 1 ("" word))',
        '(a (()) 1 "")',
        "(a (()) 1 +true)",
        "(a (()) +true word)",
        "(a (()) +true 2)",
        "(a (()) +true -0)",
        "(a (()) +true 0.0)",
        "(a (()) 1 ())",
        "(a (()) () 1)",
        "(a (()) 1 (() (x 2)))",
        "(a (()) (() (x 2)) 1)",
        "(a (()) (()))",
        "(()) (())",
        "(()) (()) (a 1)",
        "(()) 1 (())",
        '(a (()) ("" word) ())',
        '(a (()) (() (x 2)) ("" word))',
        "(a (()) 1 (x 2))",
    ],
)
@pytest.mark.parametrize(
    "parse_module", [lark_parser, hand_parse], ids=["lark", "hand"]
)
def test_arrays_reject_incompatible_element_kinds(parse_module, source):
    with pytest.raises(SxpbParseError):
        parse_module.loads(source)


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
    ("source", "expected"),
    [
        (
            "((choice) (named 9) one (middle +false) 02 +true)",
            {
                "choice": [
                    {"named": 9},
                    {"": "one"},
                    {"middle": False},
                    {"": "02"},
                    {"": "+true"},
                ]
            },
        ),
        (
            "((choice) (named one) 1 (middle +true) 2.5)",
            {
                "choice": [
                    {"named": "one"},
                    {"": 1},
                    {"middle": True},
                    {"": 2.5},
                ]
            },
        ),
        (
            "(()) (named one) +true (middle 9) 00 +01 +false",
            [
                {"named": "one"},
                {"": True},
                {"middle": 9},
                {"": False},
                {"": True},
                {"": False},
            ],
        ),
        (
            "((choice) () (named 1) (() (x 2)))",
            {
                "choice": [
                    {"": {}},
                    {"named": 1},
                    {"": {"x": 2}},
                ]
            },
        ),
        (
            "((choice) 1 (named (x 2)) 3)",
            {
                "choice": [
                    {"": 1},
                    {"named": {"x": 2}},
                    {"": 3},
                ]
            },
        ),
    ],
)
@pytest.mark.parametrize(
    "parse_module", [lark_parser, hand_parse], ids=["lark", "hand"]
)
def test_first_anonymous_controls_manyof_elements(parse_module, source, expected):
    assert parse_module.loads(source, precise=True) == expected


@pytest.mark.parametrize(
    "source",
    [
        "((choice) 1 (named word) +true)",
        "((choice) +true (named word) 2)",
        "((choice) one (named 1) ())",
        "((choice) () (named 1) one)",
        "((choice) 1 (named word) (() (x 2)))",
        "((choice) (() (x 1)) (named word) 2)",
        "((choice) (()))",
        "(()) (named word) one (middle +true) (())",
        "(()) (named word) 1 (middle +true) +false",
    ],
)
@pytest.mark.parametrize(
    "parse_module", [lark_parser, hand_parse], ids=["lark", "hand"]
)
def test_manyofs_reject_incompatible_anonymous_kinds(parse_module, source):
    with pytest.raises(SxpbParseError):
        parse_module.loads(source)


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
