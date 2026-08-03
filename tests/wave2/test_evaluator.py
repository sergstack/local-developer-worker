from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]


def _run_evaluator():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_wave2_evaluator.py")],
        text=True,
        capture_output=True,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        check=True,
    )
    return completed.stdout, json.loads(completed.stdout)


def test_frozen_wave2_evaluator_passes_all_mandatory_gates():
    first_stdout, first = _run_evaluator()
    second_stdout, second = _run_evaluator()
    assert first_stdout == second_stdout
    assert first == second
    assert first["gate_status"] == "INFORMATIONAL_ONLY"
    assert first["status"] == "pass"
    assert all(first["gates"].values())
    assert first["metrics"]["critical_file_omissions"] == 0
    assert first["metrics"]["sensitive_file_leaks"] == 0
    assert first["metrics"]["outside_root_reads"] == 0
    assert first["metrics"]["silent_exclusions"] == 0
    assert first["metrics"]["median_context_reduction"] >= 0.40
    assert first["metrics"]["reduction_at_least_0_25_rate"] >= 0.80
