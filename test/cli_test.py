import json
import os
import subprocess
import sys
from pathlib import Path


CONTENT_DIR = Path(__file__).parent / "content"


def run_cli(module, args, stdin_data=None):
    cmd = [sys.executable, "-m", module] + args
    env = os.environ.copy()
    project_root = Path(__file__).parent.parent
    src_path = str(project_root / "src")
    python_path = env.get("PYTHONPATH")
    if python_path:
        env["PYTHONPATH"] = f"{src_path}{os.pathsep}{python_path}"
    else:
        env["PYTHONPATH"] = src_path
    result = subprocess.run(
        cmd,
        input=stdin_data,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
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


def test_sxpb2sxpb():
    sxpb_content = "(key value) (another value)"
    result = run_cli("sxpb.sxpb2sxpb_main", [], stdin_data=sxpb_content)
    assert result.returncode == 0
    expected_output = "(key value)\n(another value)\n"
    assert result.stdout == expected_output


def test_sxpb2sxpb_validate_only_valid():
    sxpb_content = "(key value)"
    result = run_cli(
        "sxpb.sxpb2sxpb_main", ["--validate_only"], stdin_data=sxpb_content
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_sxpb2sxpb_validate_only_invalid():
    sxpb_content = "(key value"
    result = run_cli(
        "sxpb.sxpb2sxpb_main", ["--validate_only"], stdin_data=sxpb_content
    )
    assert result.returncode == 1
    assert result.stdout == ""
