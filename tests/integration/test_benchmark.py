import json
import statistics
import subprocess
import sys
from pathlib import Path


def test_reference_benchmark_has_twelve_observed_cases():
    root = Path(__file__).parents[2]
    completed = subprocess.run([sys.executable, "scripts/run_reference_benchmark.py"], cwd=root, capture_output=True, text=True, check=True)
    output = json.loads(completed.stdout)
    assert output["status"] == "OBSERVED"
    assert output["gate_status"] == "INFORMATIONAL_ONLY"
    assert "not used for promotion decisions" in output["measurement"]
    assert output["case_count"] == 12
    assert all("token_proxy_saving" in case for case in output["cases"])
    assert all(case["critical_omissions"] == [] for case in output["cases"])
    assert all(case["unexpected_inclusions"] == [] for case in output["cases"])
    assert all(case["minimal_context_bytes"] >= case["task_bytes"] for case in output["cases"])
    assert all(case["minimal_context_bytes"] <= case["codex_only_input_bytes"] for case in output["cases"])
    assert all(case["token_proxy_before"] >= case["token_proxy_after"] for case in output["cases"])
    assert all(case["schema_validity"] == "OBSERVED" for case in output["cases"])
    assert "upper bound" in output["measurement"]
    assert "fully reads every candidate file" in output["measurement"]
    assert set(output["class_results"]) == {"short_single_file", "multi_file", "log_heavy", "reporting"}
    for result in output["class_results"].values():
        assert result["n"] == len(result["raw_values"])
        assert result["min"] == min(result["raw_values"])
        assert result["max"] == max(result["raw_values"])
        assert result["median"] == round(statistics.median(result["raw_values"]), 4)
        assert ("LOW_N" in result["flags"]) == (result["n"] < 5)
        assert set(result["sensitivity"]) == {"x0.1", "x10"}
        sensitivity_deltas = [scaled["median_delta_percentage_points"] for scaled in result["sensitivity"].values()]
        assert ("SIZE_SENSITIVE" in result["flags"]) == any(delta > 10 for delta in sensitivity_deltas)
        assert result["economic_promotion_eligible"] == ("SIZE_SENSITIVE" not in result["flags"])
        assert set(result["selection_metrics"]) == {"excluded_file_count", "excluded_file_ratio", "critical_recall", "distractor_rejection_rate"}
    assert all(0 <= case["excluded_file_ratio"] <= 1 for case in output["cases"])
    assert all(0 <= case["critical_recall"] <= 1 for case in output["cases"])
    assert all(0 <= case["distractor_rejection_rate"] <= 1 for case in output["cases"])
    assert all(case[field] == "NOT RUN" for case in output["cases"] for field in ("fallback", "review_time", "rejected_results"))
