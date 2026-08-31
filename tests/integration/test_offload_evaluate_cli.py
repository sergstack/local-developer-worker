from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_offload_evaluate_cli_is_read_only_and_non_promoting():
    fixture = ROOT / "fixtures" / "offload_effect_study" / "dry_run_manifest.json"
    completed = subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", "offload", "evaluate"],
        input=fixture.read_text(), text=True, capture_output=True, cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "LDW_TELEMETRY_DISABLED": "1"}, check=False,
    )
    output = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert output["status"] == "partial"
    assert output["data"]["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert output["data"]["privacy"]["model_or_provider_invoked"] is False
