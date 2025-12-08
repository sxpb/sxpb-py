import os
import subprocess
import sys
from pathlib import Path
import pytest


def _run_cli_command(module, args, stdin_data=None):
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


@pytest.fixture
def run_sxpb2sxpb_tool():
    def _run(args, stdin_data=None):
        return _run_cli_command("sxpb.sxpb2sxpb_main", args, stdin_data=stdin_data)

    return _run


@pytest.fixture
def run_sxpb2json_tool():
    def _run(args, stdin_data=None):
        return _run_cli_command("sxpb.sxpb2json_main", args, stdin_data=stdin_data)

    return _run
