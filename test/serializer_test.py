import pytest

import sxpb


def test_pretty_print_indent():
    """Tests serialization with a specific positive indent."""
    data = {"a": {"b": "c"}}
    expected_output = "(a\n  (b c)\n)"
    assert sxpb.dumps(data, indent=2) == expected_output


def test_zero_indent_serialization():
    """Tests serialization with indent=0 for single-line output."""
    data = {"a": 1, "b": {"c": 3}}
    expected_output = "(a 1) (b (c 3))"
    assert sxpb.dumps(data, indent=0) == expected_output


def test_condensed_serialization():
    """Tests serialization with indent=-1 for condensed output."""
    data = {"a": 1, "b": {"c": 3}}
    expected_output = "(a 1)(b(c 3))"
    assert sxpb.dumps(data, indent=-1) == expected_output


def test_array_serialization_with_indents():
    """Tests array serialization with different indents."""
    data = {"a": [1, 2, 3]}
    # Positive indent
    expected_pretty = "(a (())\n 1\n 2\n 3\n)"
    assert sxpb.dumps(data, indent=1) == expected_pretty
    # Zero indent
    expected_zero = "(a (()) 1 2 3)"
    assert sxpb.dumps(data, indent=0) == expected_zero
    # Condensed indent
    expected_condensed = "(a(())1 2 3)"
    assert sxpb.dumps(data, indent=-1) == expected_condensed


def test_array_serialization_reconciles_first_element_kind():
    string_first = {"a": ["one", 2, True]}
    assert sxpb.loads(sxpb.dumps(string_first)) == {"a": ["one", "2", "+true"]}

    bool_first = {"a": [True, 0, 1, False]}
    assert sxpb.loads(sxpb.dumps(bool_first)) == {"a": [True, False, True, False]}

    for values in [
        [1, "one"],
        [1, True],
        [True, 2],
        [True, 0.0],
        [1, {}],
        [{}, 1],
    ]:
        with pytest.raises(TypeError, match="incompatible"):
            sxpb.dumps({"a": values})


def test_top_level_manyof_serialization():
    """Tests top-level manyof (SxpbMany) serialization with different indents."""
    data = sxpb.Many([{"a": 1}, {"b": 2}])
    # Positive indent
    expected_pretty = "(())\n(a 1)\n(b 2)"
    assert sxpb.dumps(data, indent=1) == expected_pretty
    # Zero indent
    expected_zero = "(()) (a 1) (b 2)"
    assert sxpb.dumps(data, indent=0) == expected_zero
    # Condensed indent
    expected_condensed = "(())(a 1)(b 2)"
    assert sxpb.dumps(data, indent=-1) == expected_condensed


@pytest.mark.parametrize(
    ("values", "expected_by_indent"),
    [
        (
            [1, 2],
            {
                1: "((choice)\n 1\n 2\n)",
                0: "((choice) 1 2)",
                -1: "((choice)1 2)",
            },
        ),
        (
            ["1", "2"],
            {
                1: '((choice)\n "1"\n "2"\n)',
                0: '((choice) "1" "2")',
                -1: '((choice)"1" "2")',
            },
        ),
    ],
    ids=["numbers", "numeric-looking-strings"],
)
def test_named_manyof_anonymous_scalar_roundtrip(values, expected_by_indent):
    data = {"choice": sxpb.Many([sxpb.Lone({"": value}) for value in values])}

    for indent, expected in expected_by_indent.items():
        serialized = sxpb.dumps(data, indent=indent)
        assert serialized == expected

        parsed = sxpb.loads(serialized, precise=True)
        assert isinstance(parsed, sxpb.Mesg)
        assert isinstance(parsed["choice"], sxpb.Many)
        assert parsed == data


def test_named_manyof_preserves_explicit_value_name():
    data = {"choice": sxpb.Many([sxpb.Lone({"value": 1}), sxpb.Lone({"": 2})])}
    expected_by_indent = {
        1: "((choice)\n (value 1)\n 2\n)",
        0: "((choice) (value 1) 2)",
        -1: "((choice)(value 1)2)",
    }

    for indent, expected in expected_by_indent.items():
        serialized = sxpb.dumps(data, indent=indent)
        assert serialized == expected
        assert sxpb.loads(serialized, precise=True) == data


def test_named_manyof_anonymous_message_roundtrip():
    data = {
        "choice": sxpb.Many(
            [sxpb.Lone({"": sxpb.Mesg({"a": 1})}), sxpb.Lone({"": sxpb.Mesg()})]
        )
    }
    serialized = sxpb.dumps(data, indent=0)
    assert serialized == "((choice) (() (a 1)) ())"
    assert sxpb.loads(serialized, precise=True) == data


@pytest.mark.parametrize(
    ("values", "atoms"),
    [
        ([1, 2, 3], ["1", "2", "3"]),
        (["1", "2", "3"], ['"1"', '"2"', '"3"']),
    ],
    ids=["numbers", "numeric-looking-strings"],
)
@pytest.mark.parametrize(
    "first_name", ["a", ""], ids=["named-first", "anonymous-first"]
)
def test_top_level_manyof_scalar_serialization(values, atoms, first_name):
    data = sxpb.Many(
        [sxpb.Lone({first_name: values[0]})]
        + [sxpb.Lone({"": value}) for value in values[1:]]
    )
    printed_first_name = first_name or "value"
    expected_by_indent = {
        1: f"(())\n({printed_first_name} {atoms[0]})\n{atoms[1]}\n{atoms[2]}",
        0: f"(()) ({printed_first_name} {atoms[0]}) {atoms[1]} {atoms[2]}",
        -1: f"(())({printed_first_name} {atoms[0]}){atoms[1]} {atoms[2]}",
    }
    expected_parsed = sxpb.Many(
        [sxpb.Lone({printed_first_name: values[0]})]
        + [sxpb.Lone({"": value}) for value in values[1:]]
    )

    for indent, expected in expected_by_indent.items():
        serialized = sxpb.dumps(data, indent=indent)
        assert serialized == expected
        assert sxpb.loads(serialized, precise=True) == expected_parsed


def test_top_level_array_serialization():
    """Tests top-level array (list) serialization with different indents."""
    data = [1, 2, 3]
    # Positive indent
    expected_pretty = "(())\n1\n2\n3"
    assert sxpb.dumps(data, indent=1) == expected_pretty
    # Zero indent
    expected_zero = "(()) 1 2 3"
    assert sxpb.dumps(data, indent=0) == expected_zero
    # Condensed indent: the list discriminator is complete before its elements.
    expected_condensed = "(())1 2 3"
    serialized = sxpb.dumps(data, indent=-1)
    assert serialized == expected_condensed
    assert sxpb.loads(serialized, precise=True) == data


def test_message_array_serialization():
    """Tests serialization of an array of messages with different indents."""
    data = {"messages": [{"a": 1}, {"b": 2}]}
    # Positive indent
    expected_pretty = "(messages (())\n (()\n  (a 1)\n )\n (()\n  (b 2)\n )\n)"
    assert sxpb.dumps(data, indent=1) == expected_pretty
    # Zero indent
    expected_zero = "(messages (()) (() (a 1)) (() (b 2)))"
    assert sxpb.dumps(data, indent=0) == expected_zero
    # Condensed indent: each message retains its anonymous-message wrapper.
    expected_condensed = "(messages(())(()(a 1))(()(b 2)))"
    serialized = sxpb.dumps(data, indent=-1)
    assert serialized == expected_condensed
    precise = sxpb.loads(serialized, precise=True)
    assert precise == data
    assert isinstance(precise, sxpb.Mesg)
    assert isinstance(precise["messages"], sxpb.List)


def test_condensed_message_arrays_preserve_empty_elements():
    messages = [{}, {"a": 1}, {}, {"b": 2}]
    cases = [
        (messages, "(())()(()(a 1))()(()(b 2))"),
        (
            {"messages": messages},
            "(messages(())()(()(a 1))()(()(b 2)))",
        ),
    ]

    for data, expected in cases:
        serialized = sxpb.dumps(data, indent=-1)
        assert serialized == expected
        precise = sxpb.loads(serialized, precise=True)
        assert precise == data
        assert sxpb.loads(sxpb.dumps(precise, indent=-1), precise=True) == precise


@pytest.mark.parametrize(
    "name",
    [
        "01",
        ".5",
        "-1",
        "01.2300",
        "1e9999",
        "9007199254740993",
        "-0.000000000000000000000000001",
        "+name",
        "-.name",
        ".+name",
    ],
)
def test_subnest_name_roundtrip(name):
    data = {"nest": sxpb.Nest([sxpb.Lone({name: sxpb.Nest(["leaf"])})])}

    for indent in (1, 0, -1):
        serialized = sxpb.dumps(data, indent=indent)
        assert sxpb.loads(serialized, precise=True) == data


def test_unicode_serialization():
    """Tests that Unicode characters are not escaped."""
    data = {"a": "你好"}
    expected_output = "(a 你好)"
    assert sxpb.dumps(data, indent=0) == expected_output


def test_loneof_array_option_serialization():
    data = sxpb.Lone({"my_loneof_array_option": [1, 2, 3]})
    assert (
        sxpb.dumps({"my_key": data}, indent=0)
        == "((my_key my_loneof_array_option) (()) 1 2 3)"
    )


def test_condensed_loneof_message_roundtrip():
    data = {"fruit_as": sxpb.Lone({"banana": {"count": 5, "ripeness": 0.4}})}
    serialized = sxpb.dumps(data, indent=-1)

    assert serialized == "((fruit_as banana)(count 5)(ripeness 0.4))"
    parsed = sxpb.loads(serialized, precise=True)
    assert isinstance(parsed, sxpb.Mesg)
    assert isinstance(parsed["fruit_as"], sxpb.Lone)
    assert parsed == data


def test_lone_punctuation_bare_atom_roundtrip():
    data = {"dash": "-", "dot": ".", "-": "dash", ".": "dot"}
    serialized = sxpb.dumps(data, indent=0)

    assert serialized == "(dash -) (dot .) (- dash) (. dot)"
    assert sxpb.loads(serialized, precise=True) == data


def test_canonical_string_atoms():
    data = {
        "strings": ["1", "two words", "bare"],
        "flag_strings": ["+true", "+false", "true"],
        "needs_quote": "1 2",
    }
    expected_output = (
        '(strings (()) "1" "two words" bare) '
        '(flag_strings (()) "+true" "+false" true) '
        '(needs_quote "1 2")'
    )
    assert sxpb.dumps(data, indent=0) == expected_output


def test_canonical_quoted_field_names():
    data = {"two words": "ok", "1": "one"}
    assert sxpb.dumps(data, indent=0) == '("two words" ok) ("1" one)'


def test_canonical_top_level_nest():
    data = sxpb.Nest(
        [
            "black",
            {"white": sxpb.Nest(["bear"])},
            {"grass": sxpb.Nest(["green", "verdant"])},
        ]
    )
    expected_output = '("")\nblack\n(white bear)\n(grass green verdant)'
    assert sxpb.dumps(data, indent=1) == expected_output


def test_canonical_anonymous_nest():
    data = sxpb.Nest([sxpb.Nest(["content"]), {"": sxpb.Nest([])}])
    expected_output = '("")\n("" ("") content)\n("" (""))'
    assert sxpb.dumps(data, indent=1) == expected_output
