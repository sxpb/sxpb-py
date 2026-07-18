import json
import subprocess

import pytest

# Test cases: (sxpb_content, json_content)
TEST_CASES = [
    (
        '(name "John Doe") (age 30)',
        '{"name": "John Doe", "age": 30}',
    ),
    (
        '(parts (()) (() ("a" 1)) (() ("b" 2)))',
        '{"parts": [{"a": 1}, {"b": 2}]}',
    ),
]


@pytest.mark.parametrize("sxpb_content, json_content", TEST_CASES)
def test_sxpb2json(sxpb_content, json_content):
    """Test the sxpb2json command-line tool."""
    process = subprocess.run(
        ["python", "-m", "sxpb.sxpb2json_main"],
        input=sxpb_content,
        capture_output=True,
        text=True,
        check=True,
    )
    # Strip to remove any trailing newline
    assert json.loads(process.stdout) == json.loads(json_content)


@pytest.mark.parametrize("sxpb_content, json_content", TEST_CASES)
def test_json2sxpb(sxpb_content, json_content):
    """Test the json2sxpb command-line tool."""
    process = subprocess.run(
        ["python", "-m", "sxpb.json2sxpb_main"],
        input=json_content,
        capture_output=True,
        text=True,
        check=True,
    )
    # Just checking for basic equivalence, not perfect formatting.
    # We'll reload the sxpb output and compare to the parsed original sxpb.
    from sxpb.parse import loads
    from sxpb.jsonutil import to_plain_types

    original_parsed = to_plain_types(loads(sxpb_content))
    output_parsed = to_plain_types(loads(process.stdout))
    assert output_parsed == original_parsed
