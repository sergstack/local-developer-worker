import json
import os
import subprocess
import sys
from pathlib import Path


def _run(root, args, payload):
    return subprocess.run([sys.executable, "-m", "local_developer_worker.cli", *args], input=json.dumps(payload), text=True, capture_output=True, cwd=root, env={**os.environ, "PYTHONPATH": str(root / "src")}, check=False)


def test_zero_timeout_returns_non_success_with_fallback(tmp_path):
    root = Path(__file__).parents[2]
    policy = tmp_path / "timeout.toml"
    policy.write_text("[limits]\ntimeout_seconds = 0\n[fallback]\non_timeout = 'codex'\n")
    completed = _run(root, ["log", "parse"], {"text": "INFO ok", "policy_path": str(policy)})
    output = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert output["status"] == "timeout"
    assert output["data"]["fallback"] == "codex"


def test_cli_blocks_repository_outside_default_allowlist(tmp_path):
    root = Path(__file__).parents[2]
    completed = _run(root, ["files", "inventory"], {"repository_root": str(tmp_path)})
    output = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert output["status"] == "policy_blocked"
    assert output["errors"][0]["code"] == "repository_root_not_allowed"
