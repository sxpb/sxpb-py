from collections.abc import Mapping
from sxpb import parser, serializer
from sxpb.types import SxpbNest
import pytest
from lark import UnexpectedToken, UnexpectedCharacters
import textwrap


def test_user_example():
    sxpb_text = textwrap.dedent("""
        (my_nest ("")
         t
         ("" u v)
         (w a b)
         (x "" c d)
         ("y z" "" e f)
        )
    """)
    data = parser.loads(sxpb_text, precise=True)
    assert isinstance(data, Mapping)
    nest = data["my_nest"]

    # t
    assert "t" in nest
    assert nest["t"] is None

    # ("" u v) -> "u v"
    assert "u v" in nest
    assert nest["u v"] is None

    # (w a b) -> w -> {a: None, b: None}
    assert "w" in nest
    w = nest["w"]
    assert "a" in w
    assert w["a"] is None
    assert "b" in w
    assert w["b"] is None

    # (x "" c d) -> x -> {"c d": None}
    assert "x" in nest
    x = nest["x"]
    assert "c d" in x
    assert x["c d"] is None

    # ("y z" "" e f) -> "y z" -> {"e f": None}
    assert "y z" in nest
    yz = nest["y z"]
    assert "e f" in yz
    assert yz["e f"] is None

    # Serialization test
    generated_sxpb = serializer.dumps(data, indent=1)

    # Check output format
    print(generated_sxpb)

    assert '(my_nest ("")' in generated_sxpb
    assert " t" in generated_sxpb
    assert ' ("" u v)' in generated_sxpb
    assert " (w a b)" in generated_sxpb
    assert ' (x "" c d)' in generated_sxpb
    assert ' ("y z" "" e f)' in generated_sxpb


def test_nest_roundtrip():
    # Construct a Nest object programmatically
    nest = SxpbNest(
        {
            "simple": None,
            "sub": SxpbNest(
                {
                    "key1": None,
                    "key2": None,
                }
            ),
            "str_field": SxpbNest({"some string value": None}),
            "quoted string": None,
            "empty_str": SxpbNest({"": None}),
        }
    )

    # Wrap in a message structure as Nests are usually fields
    data = {"my_nest": nest}

    serialized = serializer.dumps(data, indent=1)

    assert '(my_nest ("")' in serialized
    assert "simple" in serialized
    assert "(sub key1 key2)" in serialized  # 2 keys -> inline
    assert '(str_field "" some string value)' in serialized

    # Leaf with spaces "quoted string" -> ("" quoted string)
    assert '("" quoted string)' in serialized

    assert '(empty_str "")' in serialized

    # Parse back
    loaded = parser.loads(serialized, precise=True)
    assert isinstance(loaded, Mapping)
    assert loaded["my_nest"] == nest


def test_formatting_rules():
    # 4 strings -> multiline
    nest = SxpbNest({"a": None, "b": None, "c": None, "d": None})
    data = {"test": nest}
    serialized = serializer.dumps(data, indent=1)
    assert '(test ("")\n a\n b\n c\n d\n)' in serialized

    # 3 strings -> inline
    nest3 = SxpbNest({"a": None, "b": None, "c": None})
    data3 = {"test": nest3}
    serialized3 = serializer.dumps(data3, indent=1)
    assert '(test ("") a b c)' in serialized3

    # subnest -> multiline
    nest_mixed = SxpbNest({"a": None, "sub": SxpbNest({"x": None})})
    data_mixed = {"test": nest_mixed}
    serialized_mixed = serializer.dumps(data_mixed, indent=1)
    assert '(test ("")\n a\n (sub x)\n)' in serialized_mixed


def test_illegal_subnest_in_string_field():
    # Expect parse error
    sxpb_text = '(my_nest ("") (my_string "" (illegal)))'

    with pytest.raises((UnexpectedToken, UnexpectedCharacters)):
        parser.loads(sxpb_text, precise=True)

    # Also test legal atoms
    legal_text = '(my_nest ("") (my_string "" legal atoms))'
    data = parser.loads(legal_text, precise=True)
    assert isinstance(data, Mapping)
    assert "my_nest" in data
    assert isinstance(data["my_nest"], Mapping)
    assert "my_string" in data["my_nest"]
    assert "legal atoms" in data["my_nest"]["my_string"]


def test_toplevel_nest():
    sxpb_text = textwrap.dedent("""
        ("")
        key1
        (key2 val2)
    """)
    data = parser.loads(sxpb_text, precise=True)
    assert isinstance(data, SxpbNest)
    assert "key1" in data
    assert data["key1"] is None
    assert "key2" in data
    assert isinstance(data["key2"], SxpbNest)
    assert "val2" in data["key2"]

    # Roundtrip
    serialized = serializer.dumps(data, indent=1)
    print(serialized)
    assert serialized.strip().startswith('("")')
    assert "key1" in serialized
    assert "(key2 val2)" in serialized

    loaded = parser.loads(serialized, precise=True)
    assert loaded == data
