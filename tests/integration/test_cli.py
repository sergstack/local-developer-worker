import json
import subprocess
import sys
import os
from pathlib import Path


def test_cli_emits_json_only_on_stdout():
    root = Path(__file__).parents[2]
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    completed = subprocess.run([sys.executable, "-m", "local_developer_worker.cli", "log", "parse"], input='{"text":"ERROR boom"}', text=True, capture_output=True, cwd=root, env=env, check=False)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["tool"] == "structured_log_parser"
    assert completed.stderr == ""
