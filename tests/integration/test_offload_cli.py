from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_offload_cli_returns_visible_block_when_local_and_frontier_are_forbidden(tmp_path):
    policy = tmp_path / "policy.toml"
    policy.write_text("[automatic]\nollama_readonly_advisory = false\n[ollama]\nenabled = false\n")
    payload = {
        "task": "Classify one bounded item",
        "task_class": "bounded_text_classification",
        "risk_floor": "balanced",
        "offload_mode": "local_first",
        "verification_kind": "execution",
        "fallback_policy": {"deterministic": "skip", "frontier": "forbidden"},
        "policy_revision": "a" * 64,
        "policy_path": str(policy),
    }
    completed = subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", "offload", "execute"],
        input=json.dumps(payload), text=True, capture_output=True, cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, check=False,
    )
    output = json.loads(completed.stdout)

    assert completed.returncode == 2
    assert output["status"] == "policy_blocked"
    assert output["data"]["local_capability"]["runtime"] == "policy_blocked"
    assert output["errors"] == [{"code": "frontier_fallback_forbidden"}]
