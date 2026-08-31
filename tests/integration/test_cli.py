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


def test_candidate_lesson_validator_is_non_promoting():
    root = Path(__file__).parents[2]
    env = {**os.environ, "PYTHONPATH": str(root / "src"), "LDW_TELEMETRY_DISABLED": "1"}
    payload = {
        "contract_version": "1.0.0", "allowed_evidence_refs": ["EV_001"], "candidate": {
            "candidate_id": "CANDIDATE_001", "trigger": "repeated_tool_call", "observed_problem": "Repeated execution signal.",
            "human_correction": "Use deterministic path first.", "rework_class": "execution",
            "generalizable_rule": "Use known deterministic path before retrying.", "scope": "LDW execution handling",
            "counterexamples": ["Do not apply when unavailable."], "evidence_refs": ["EV_001"],
            "occurrence_count": 3, "candidate_destination": "execution_handling", "confidence": "low",
        },
    }
    completed = subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", "learn", "validate-candidate"],
        input=json.dumps(payload), text=True, capture_output=True, cwd=root, env=env, check=False,
    )
    assert completed.returncode == 0
    data = json.loads(completed.stdout)["data"]
    assert data["validation"]["promotion_status"] == "candidate_only"
    assert data["privacy"]["model_invoked"] is False


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
