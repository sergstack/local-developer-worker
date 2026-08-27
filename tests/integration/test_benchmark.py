import json
import statistics
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def _without_latency(output):
    normalized = json.loads(json.dumps(output))
    for case in normalized["cases"]:
        case["worker_latency_ms"] = None
        case["metrics"]["task_latency_ms"]["value"] = None
    return normalized


def test_reference_benchmark_has_twelve_observed_cases():
    root = Path(__file__).parents[2]
    completed = subprocess.run([sys.executable, "scripts/run_reference_benchmark.py"], cwd=root, capture_output=True, text=True, check=True)
    output = json.loads(completed.stdout)
    schema = json.loads((root / "schemas" / "context_efficiency_measurement.schema.json").read_text())
    Draft202012Validator(schema).validate(output)
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
    assert output["measurement_contract_version"] == "1.0.0"
    assert output["baseline_id"] == "context-efficiency-vnext-issue-23"
    assert output["corpus"]["case_count"] == output["case_count"]
    assert len(output["corpus"]["manifest_sha256"]) == 64
    assert len(output["source_revision"]["runner_sha256"]) == 64
    for case in output["cases"]:
        metrics = case["metrics"]
        assert metrics["candidate_context_bytes"]["status"] == "observed"
        assert metrics["estimated_input_tokens_before"]["status"] == "estimated"
        assert "not a provider token count" in metrics["estimated_input_tokens_before"]["method"]
        assert metrics["provider_tokens"] == {"status": "unavailable", "unit": "tokens", "value": None}
        assert metrics["provider_cost"] == {"status": "unavailable", "unit": "currency", "value": None}
        assert metrics["coding_agent_tool_calls"]["status"] == "not_measured"
        assert metrics["task_success"]["status"] == "not_measured"


def test_reference_benchmark_is_repeatable_except_for_observed_latency():
    root = Path(__file__).parents[2]
    command = [sys.executable, "scripts/run_reference_benchmark.py"]
    first = json.loads(subprocess.run(command, cwd=root, capture_output=True, text=True, check=True).stdout)
    second = json.loads(subprocess.run(command, cwd=root, capture_output=True, text=True, check=True).stdout)

    assert _without_latency(first) == _without_latency(second)
