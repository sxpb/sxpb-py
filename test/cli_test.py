import json
import subprocess
import sys
from pathlib import Path


CONTENT_DIR = Path(__file__).parent / "content"


def run_cli(module, args, stdin_data=None):
    cmd = [sys.executable, "-m", module] + args
    result = subprocess.run(
        cmd,
        input=stdin_data,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result


def test_sxpb2json_stdin_stdout():
    sxpb_path = CONTENT_DIR / "array.sxpb"
    json_path = CONTENT_DIR / "array.json"

    with open(sxpb_path, "r") as f:
        sxpb_content = f.read()

    result = run_cli("sxpb.sxpb2json_main", [], stdin_data=sxpb_content)

    assert result.returncode == 0

    generated_json = json.loads(result.stdout)
    expected_json = json.loads(json_path.read_text())

    assert generated_json == expected_json


def test_sxpb2json_file_args(tmp_path):
    sxpb_path = CONTENT_DIR / "array.sxpb"
    json_path = CONTENT_DIR / "array.json"

    out_path = tmp_path / "output.json"

    result = run_cli("sxpb.sxpb2json_main", [str(sxpb_path), str(out_path)])

    assert result.returncode == 0

    generated_json = json.loads(out_path.read_text())
    expected_json = json.loads(json_path.read_text())

    assert generated_json == expected_json


def test_sxpb2json_indent_arg():
    sxpb_content = "(key value)"
    result = run_cli("sxpb.sxpb2json_main", ["--indent", "2"], stdin_data=sxpb_content)

    assert result.returncode == 0
    expected_output = '{\n  "key": "value"\n}'
    assert result.stdout == expected_output
