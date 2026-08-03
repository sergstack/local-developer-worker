import json
import os
import subprocess
import sys
from pathlib import Path


def test_disabled_capability_returns_policy_blocked(tmp_path):
    policy = tmp_path / "policy.toml"
    policy.write_text("[automatic]\nstructured_log_parser = false\n[fallback]\non_policy_violation = 'codex'\n")
    payload = json.dumps({"text": "INFO ok", "policy_path": str(policy)})
    root = Path(__file__).parents[2]
    completed = subprocess.run([sys.executable, "-m", "local_developer_worker.cli", "log", "parse"], input=payload, text=True, capture_output=True, cwd=root, env={**os.environ, "PYTHONPATH": str(root / "src")}, check=False)
    output = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert output["status"] == "policy_blocked"
    assert output["data"]["fallback"] == "codex"
