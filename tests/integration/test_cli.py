import json
import subprocess
import sys
import os
from pathlib import Path

from local_developer_worker import cli
from local_developer_worker.contracts import result


def test_cli_emits_json_only_on_stdout():
    root = Path(__file__).parents[2]
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    completed = subprocess.run([sys.executable, "-m", "local_developer_worker.cli", "log", "parse"], input='{"text":"ERROR boom"}', text=True, capture_output=True, cwd=root, env=env, check=False)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["tool"] == "structured_log_parser"
    assert completed.stderr == ""


def test_cli_flushes_terminal_tool_result(monkeypatch):
    class RecordingStdout:
        def __init__(self):
            self.text = ""
            self.flush_count = 0

        def write(self, value):
            self.text += value
            return len(value)

        def flush(self):
            self.flush_count += 1

    stdout = RecordingStdout()
    monkeypatch.setenv("LDW_TELEMETRY_DISABLED", "1")
    monkeypatch.setattr(cli.sys, "stdout", stdout)

    exit_code = cli._emit(result("doctor", "local", "{}", {"ready": True}), ("doctor",), {}, "{}", 0.0)

    assert exit_code == 0
    assert stdout.flush_count == 1
    assert json.loads(stdout.text)["data"] == {"ready": True}
