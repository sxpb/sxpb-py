from cli_test import run_cli


def test_unclosed_parenthesis():
    sxpb_content = "(key value"
    result = run_cli(
        "sxpb.sxpb2sxpb_main", ["--validate_only"], stdin_data=sxpb_content
    )
    assert result.returncode == 1
    assert "Validation failed:" in result.stderr
    assert "Unexpected end of input." in result.stderr
    assert "a closing parenthesis `)`" in result.stderr


def test_unexpected_token():
    sxpb_content = "(key value))"
    result = run_cli(
        "sxpb.sxpb2sxpb_main", ["--validate_only"], stdin_data=sxpb_content
    )
    assert result.returncode == 1
    assert "Validation failed:" in result.stderr
    assert "Found an unexpected character ')'" in result.stderr
    assert "an opening parenthesis `(`" in result.stderr


def test_empty_string_as_field_name():
    sxpb_content = '("" value)'
    result = run_cli(
        "sxpb.sxpb2sxpb_main", ["--validate_only"], stdin_data=sxpb_content
    )
    assert result.returncode == 1
    assert "Validation failed:" in result.stderr
    assert "Found an unexpected character '\"'" in result.stderr
    assert "a non-empty quoted string for a field name" in result.stderr
