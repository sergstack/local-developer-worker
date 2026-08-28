import json
from pathlib import Path

import pytest

from local_developer_worker.context_efficiency_replay import analyze_replay


def test_dry_replay_is_bounded_and_cannot_promote():
    data = json.loads((Path(__file__).parents[2] / "fixtures/context_efficiency_replay/dry_run_manifest.json").read_text())
    result = analyze_replay(data)
    assert result["verdict"] == "REVISE"
    assert result["provider_calls"] is False
    assert result["task_success_regression"] is False
    assert result["baseline_revision"] == "baseline-fixture-v1"
    assert result["candidate_revision"] == "candidate-fixture-v1"
    assert result["pair_outcomes"] == [
        {"pair_id": "TASK-001", "baseline_task_accepted": True, "candidate_task_accepted": True, "delta_percent": {"context_bytes": -40.0, "tool_calls": -33.3333, "latency_ms": -20.0}},
        {"pair_id": "TASK-002", "baseline_task_accepted": True, "candidate_task_accepted": True, "delta_percent": {"context_bytes": -37.5, "tool_calls": 0.0, "latency_ms": -5.5556}},
    ]


def test_replay_requires_shared_environment_budget_timeout_and_verifier():
    data = json.loads((Path(__file__).parents[2] / "fixtures/context_efficiency_replay/dry_run_manifest.json").read_text())
    del data["pairs"][0]["verifier_id"]
    with pytest.raises(ValueError, match="invalid_replay_pair"):
        analyze_replay(data)


def test_replay_requires_explicit_baseline_and_candidate_revisions():
    data = json.loads((Path(__file__).parents[2] / "fixtures/context_efficiency_replay/dry_run_manifest.json").read_text())
    del data["baseline_revision"]
    with pytest.raises(ValueError, match="invalid_replay_manifest"):
        analyze_replay(data)


def test_synthetic_matched_replay_preserves_agent_metrics_and_outliers_without_promotion():
    data = json.loads((Path(__file__).parents[2] / "fixtures/context_efficiency_replay/synthetic_matched_replay_manifest.json").read_text())
    result = analyze_replay(data)
    assert result["verdict"] == "REVISE"
    assert result["provider_calls"] is False
    assert result["task_success_regression"] is False
    assert result["median_delta_percent"] == {"context_bytes": -20.0, "tool_calls": -12.5, "latency_ms": -10.0}
    assert result["pair_outcomes"][2] == {
        "pair_id": "SYNTHETIC-003",
        "baseline_task_accepted": True,
        "candidate_task_accepted": True,
        "delta_percent": {"context_bytes": 0.0, "tool_calls": 40.0, "latency_ms": 50.0},
    }


def test_synthetic_replay_stops_live_verdict_on_required_context_regression():
    data = json.loads((Path(__file__).parents[2] / "fixtures/context_efficiency_replay/synthetic_matched_replay_manifest.json").read_text())
    data["mode"] = "live"
    data["pairs"][2]["candidate"]["task_accepted"] = False
    result = analyze_replay(data)
    assert result["verdict"] == "STOP"
    assert result["task_success_regression"] is True


def _approved_live_manifest():
    data = json.loads((Path(__file__).parents[2] / "fixtures/context_efficiency_replay/dry_run_manifest.json").read_text())
    data["contract_version"] = "1.1.0"
    data["mode"] = "live"
    data["evidence_status"] = "observed"
    data["owner_approval_id"] = "owner-approved-materiality-v1"
    data["materiality_threshold_percent"] = {"context_bytes": 20, "tool_calls": 10, "latency_ms": 5}
    for pair in data["pairs"]:
        pair["baseline_evidence_id"] = f"{pair['pair_id']}-baseline-evidence"
        pair["candidate_evidence_id"] = f"{pair['pair_id']}-candidate-evidence"
    return data


def test_v1_live_manifest_cannot_promote_without_materiality_contract():
    data = json.loads((Path(__file__).parents[2] / "fixtures/context_efficiency_replay/dry_run_manifest.json").read_text())
    data["mode"] = "live"
    assert analyze_replay(data)["verdict"] == "REVISE"


def test_v11_live_manifest_requires_observed_evidence_and_all_material_thresholds_for_pass():
    data = _approved_live_manifest()
    result = analyze_replay(data)
    assert result["verdict"] == "PASS"
    assert result["materiality"] == {
        "approval_id": "owner-approved-materiality-v1",
        "evidence_status": "observed",
        "threshold_percent": {"context_bytes": 20, "tool_calls": 10, "latency_ms": 5},
        "all_required_metrics_met": True,
    }

    data["evidence_status"] = "synthetic"
    assert analyze_replay(data)["verdict"] == "REVISE"

    data = _approved_live_manifest()
    data["materiality_threshold_percent"]["tool_calls"] = 40
    assert analyze_replay(data)["verdict"] == "REVISE"


def test_v11_live_manifest_requires_pair_evidence_ids_and_positive_thresholds():
    data = _approved_live_manifest()
    del data["pairs"][0]["baseline_evidence_id"]
    with pytest.raises(ValueError, match="invalid_replay_pair"):
        analyze_replay(data)

    data = _approved_live_manifest()
    data["materiality_threshold_percent"]["latency_ms"] = 0
    with pytest.raises(ValueError, match="invalid_replay_manifest"):
        analyze_replay(data)
