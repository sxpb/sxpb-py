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
