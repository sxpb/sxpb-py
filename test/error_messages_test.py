def test_unclosed_parenthesis(run_sxpb2sxpb_tool):
    sxpb_content = "(missing right parenthesis"
    result = run_sxpb2sxpb_tool(["--validate_only"], stdin_data=sxpb_content)
    assert result.returncode == 1
    assert "Validation failed:" in result.stderr
    assert "Unexpected end of input." in result.stderr
    assert "a closing parenthesis `)`" in result.stderr


def test_unexpected_token(run_sxpb2sxpb_tool):
    sxpb_content = "(extra right parenthesis))"
    result = run_sxpb2sxpb_tool(["--validate_only"], stdin_data=sxpb_content)
    assert result.returncode == 1
    assert "Validation failed:" in result.stderr
    assert "Found an unexpected character ')'" in result.stderr
    assert "an opening parenthesis `(`" in result.stderr


def test_empty_string_as_field_name(run_sxpb2sxpb_tool):
    sxpb_content = '("" value)'
    result = run_sxpb2sxpb_tool(["--validate_only"], stdin_data=sxpb_content)
    assert result.returncode == 1
    assert "Validation failed:" in result.stderr
    assert "Found an unexpected character" in result.stderr
