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


def test_top_level_list_serialization():
    """Tests top-level list serialization with different indents."""
    data = [{"a": 1}, {"b": 2}]
    # Positive indent
    expected_pretty = "(a 1)\n(b 2)"
    assert sxpb.dumps(data, indent=1) == expected_pretty
    # Zero indent
    expected_zero = "(a 1) (b 2)"
    assert sxpb.dumps(data, indent=0) == expected_zero
    # Condensed indent
    expected_condensed = "(a 1)(b 2)"
    assert sxpb.dumps(data, indent=-1) == expected_condensed


def test_message_array_serialization():
    """Tests serialization of an array of messages with different indents."""
    data = {"messages": [{"a": 1}, {"b": 2}]}
    # Positive indent
    expected_pretty = "(messages (())\n (()\n  (a 1)\n )\n (()\n  (b 2)\n )\n)"
    assert sxpb.dumps(data, indent=1) == expected_pretty
    # Zero indent
    expected_zero = "(messages (()) (() (a 1)) (() (b 2)))"
    assert sxpb.dumps(data, indent=0) == expected_zero
    # Condensed indent
    expected_condensed = "(messages(())(()(a 1)(b 2)))"
    assert sxpb.dumps(data, indent=-1) == expected_condensed


def test_unicode_serialization():
    """Tests that Unicode characters are not escaped."""
    data = {"a": "你好"}
    expected_output = "(a 你好)"
    assert sxpb.dumps(data, indent=0) == expected_output
