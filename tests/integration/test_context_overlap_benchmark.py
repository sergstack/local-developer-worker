import json
import subprocess
import sys
from pathlib import Path


def test_overlap_extension_preserves_original_baseline_and_measures_reduction():
    root = Path(__file__).parents[2]
    original = json.loads(subprocess.run([sys.executable, "scripts/run_reference_benchmark.py"], cwd=root, capture_output=True, text=True, check=True).stdout)
    overlap = json.loads(subprocess.run([sys.executable, "scripts/run_context_overlap_benchmark.py"], cwd=root, capture_output=True, text=True, check=True).stdout)

    assert original["baseline_id"] == "context-efficiency-vnext-issue-23"
    assert overlap["measurement_contract_version"] == "1.1.0"
    assert overlap["baseline_reference"] == original["baseline_id"]
    assert all(case["critical_recall"] == 1 for case in overlap["cases"])
    assert [case["context_reduction"] for case in overlap["cases"][:2]] == [0.5, 0.5]
    assert overlap["cases"][2]["context_reduction"] == 0.0
    assert all(case["redundant_content_exclusions"] for case in overlap["cases"][:2])
    assert overlap["cases"][2]["redundant_content_exclusions"] == []
