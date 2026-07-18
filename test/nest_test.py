from collections.abc import Mapping, Sequence
from sxpb import SxpbParseError, parse, serialize
from sxpb.types import SxpbNest, SxpbMesg
import pytest
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
    data = parse.loads(sxpb_text, precise=True)
    assert isinstance(data, (dict, SxpbMesg))
    nest = data["my_nest"]
    assert isinstance(nest, Sequence)

    # t
    assert "t" in nest

    # ("" u v) -> "u v"
    assert "u v" in nest

    # (w a b) -> w -> [a, b]
    # We need to find the dict {w: ...} in the list
    w_item = next(item for item in nest if isinstance(item, Mapping) and "w" in item)
    w = w_item["w"]
    assert "a" in w
    assert "b" in w

    # (x "" c d) -> x -> ["c d"]
    x_item = next(item for item in nest if isinstance(item, Mapping) and "x" in item)
    x = x_item["x"]
    assert "c d" in x
    assert len(x) == 1

    # ("y z" "" e f) -> "y z" -> ["e f"]
    yz_item = next(item for item in nest if isinstance(item, Mapping) and "y z" in item)
    yz = yz_item["y z"]
    assert "e f" in yz
    assert len(yz) == 1

    # Serialization test
    generated_sxpb = serialize.dumps(data, indent=1)

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
        [
            "simple",
            {"sub": SxpbNest(["key1", "key2"])},
            {"str_field": SxpbNest(["some string value"])},
            "quoted string",
            {"empty_str": SxpbNest([""])},
        ]
    )

    # Wrap in a message structure as Nests are usually fields
    data = {"my_nest": nest}

    serialized = serialize.dumps(data, indent=1)

    assert '(my_nest ("")' in serialized
    assert "simple" in serialized
    assert "(sub key1 key2)" in serialized  # 2 keys -> inline
    assert '(str_field "" some string value)' in serialized

    # Leaf with spaces "quoted string" -> ("" quoted string)
    assert '("" quoted string)' in serialized

    assert '(empty_str "")' in serialized

    # Parse back
    loaded = parse.loads(serialized, precise=True)
    assert isinstance(loaded, (dict, SxpbMesg))
    assert loaded["my_nest"] == nest


def test_formatting_rules():
    # 4 strings -> multiline
    nest = SxpbNest(["a", "b", "c", "d"])
    data = {"test": nest}
    serialized = serialize.dumps(data, indent=1)
    assert '(test ("")\n a\n b\n c\n d\n)' in serialized

    # 3 strings -> inline
    nest3 = SxpbNest(["a", "b", "c"])
    data3 = {"test": nest3}
    serialized3 = serialize.dumps(data3, indent=1)
    assert '(test ("") a b c)' in serialized3

    # subnest -> multiline
    nest_mixed = SxpbNest(["a", {"sub": SxpbNest(["x"])}])
    data_mixed = {"test": nest_mixed}
    serialized_mixed = serialize.dumps(data_mixed, indent=1)
    assert '(test ("")\n a\n (sub x)\n)' in serialized_mixed


def test_illegal_subnest_in_string_field():
    # Expect parse error
    sxpb_text = '(my_nest ("") (my_string "" (illegal)))'

    with pytest.raises(SxpbParseError):
        parse.loads(sxpb_text, precise=True)

    # Also test legal atoms
    legal_text = '(my_nest ("") (my_string "" legal atoms))'
    data = parse.loads(legal_text, precise=True)
    assert isinstance(data, (dict, SxpbMesg))
    assert "my_nest" in data
    nest = data["my_nest"]
    assert isinstance(nest, Sequence)
    item = next(
        item for item in nest if isinstance(item, Mapping) and "my_string" in item
    )
    assert "legal atoms" in item["my_string"]


def test_toplevel_nest():
    sxpb_text = textwrap.dedent("""
        ("")
        key1
        (key2 val2)
    """)
    data = parse.loads(sxpb_text, precise=True)
    assert isinstance(data, SxpbNest)
    assert "key1" in data

    key2_item = next(
        item for item in data if isinstance(item, Mapping) and "key2" in item
    )
    key2 = key2_item["key2"]
    assert isinstance(key2, SxpbNest)
    assert "val2" in key2

    # Roundtrip
    serialized = serialize.dumps(data, indent=1)
    print(serialized)
    assert serialized.strip().startswith('("")')
    assert "key1" in serialized
    assert "(key2 val2)" in serialized

    loaded = parse.loads(serialized, precise=True)
    assert loaded == data
