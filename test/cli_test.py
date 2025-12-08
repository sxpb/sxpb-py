import json
from pathlib import Path


CONTENT_DIR = Path(__file__).parent / "content"


def test_sxpb2json_stdin_stdout(run_sxpb2json_tool):
    sxpb_path = CONTENT_DIR / "array.sxpb"
    json_path = CONTENT_DIR / "array.json"

    with open(sxpb_path, "r") as f:
        sxpb_content = f.read()

    result = run_sxpb2json_tool([], stdin_data=sxpb_content)

    assert result.returncode == 0

    generated_json = json.loads(result.stdout)
    expected_json = json.loads(json_path.read_text())

    assert generated_json == expected_json


def test_sxpb2json_file_args(tmp_path, run_sxpb2json_tool):
    sxpb_path = CONTENT_DIR / "array.sxpb"
    json_path = CONTENT_DIR / "array.json"

    out_path = tmp_path / "output.json"

    result = run_sxpb2json_tool([str(sxpb_path), str(out_path)])

    assert result.returncode == 0

    generated_json = json.loads(out_path.read_text())
    expected_json = json.loads(json_path.read_text())

    assert generated_json == expected_json


def test_sxpb2json_indent_arg(run_sxpb2json_tool):
    sxpb_content = "(key value)"
    result = run_sxpb2json_tool(["--indent", "2"], stdin_data=sxpb_content)

    assert result.returncode == 0
    expected_output = '{\n  "key": "value"\n}'
    assert result.stdout == expected_output


def test_sxpb2sxpb(run_sxpb2sxpb_tool):
    sxpb_content = "(key value) (another value)"
    result = run_sxpb2sxpb_tool([], stdin_data=sxpb_content)
    assert result.returncode == 0
    expected_output = "(key value)\n(another value)\n"
    assert result.stdout == expected_output


def test_sxpb2sxpb_validate_only_valid(run_sxpb2sxpb_tool):
    sxpb_content = "(key value)"
    result = run_sxpb2sxpb_tool(["--validate_only"], stdin_data=sxpb_content)
    assert result.returncode == 0
    assert result.stdout == ""


def test_sxpb2sxpb_validate_only_invalid(run_sxpb2sxpb_tool):
    sxpb_content = "(key value"
    result = run_sxpb2sxpb_tool(["--validate_only"], stdin_data=sxpb_content)
    assert result.returncode == 1
    assert result.stdout == ""
