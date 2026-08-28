import json
from pathlib import Path

import pytest

from local_developer_worker.context_efficiency_replay import analyze_replay, build_replay_manifest, observe_agent_jsonl


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


def _capture(pair_id, arm, **overrides):
    value = {
        "pair_id": pair_id,
        "arm": arm,
        "evidence_id": f"{pair_id}-{arm}-evidence",
        "task_id": f"{pair_id}-task",
        "environment_revision": "isolated-worktree-v1",
        "budget": 100,
        "timeout_ms": 1000,
        "verifier_id": "deterministic-verifier-v1",
        "context_bytes": 1000 if arm == "baseline" else 600,
        "estimated_input_tokens": 250 if arm == "baseline" else 150,
        "observed_input_tokens": 230 if arm == "baseline" else 140,
        "files_selected": 4 if arm == "baseline" else 2,
        "context_expansions": 1,
        "tool_calls": 10 if arm == "baseline" else 6,
        "latency_ms": 100 if arm == "baseline" else 80,
        "task_accepted": True,
        "provider_cost_usd": 0.02 if arm == "baseline" else 0.01,
    }
    value.update(overrides)
    return value


def _capture_study(*captures):
    return {
        "contract_version": "1.1.0",
        "mode": "live",
        "baseline_revision": "baseline-revision-v1",
        "candidate_revision": "candidate-revision-v1",
        "evidence_status": "observed",
        "owner_approval_id": "owner-approved-replay-v1",
        "materiality_threshold_percent": {"context_bytes": 20, "tool_calls": 10, "latency_ms": 5},
        "captures": list(captures),
    }


def test_capture_builds_pass_eligible_manifest_from_aggregate_arms_only():
    manifest = build_replay_manifest(_capture_study(_capture("PAIR-002", "candidate"), _capture("PAIR-001", "baseline"), _capture("PAIR-002", "baseline"), _capture("PAIR-001", "candidate")))
    assert [pair["pair_id"] for pair in manifest["pairs"]] == ["PAIR-001", "PAIR-002"]
    assert manifest["pairs"][0]["baseline"] == {"context_bytes": 1000, "tool_calls": 10, "latency_ms": 100, "task_accepted": True}
    assert analyze_replay(manifest)["verdict"] == "PASS"


@pytest.mark.parametrize("mutation", [
    lambda study: study["captures"][0].update({"raw_transcript": "must-not-be-accepted"}),
    lambda study: study["captures"][1].update({"task_id": "different-task"}),
    lambda study: study["captures"][1].update({"evidence_id": study["captures"][0]["evidence_id"]}),
    lambda study: study.update({"candidate_revision": study["baseline_revision"]}),
    lambda study: study["captures"].pop(),
])
def test_capture_rejects_raw_payload_and_nonmatched_arms(mutation):
    study = _capture_study(_capture("PAIR-001", "baseline"), _capture("PAIR-001", "candidate"))
    mutation(study)
    with pytest.raises(ValueError, match="invalid_capture_study"):
        build_replay_manifest(study)


def test_agent_observer_returns_only_aggregate_tool_and_token_evidence():
    events = "\n".join(json.dumps(event) for event in [
        {"type": "thread.started", "thread_id": "must-not-leak"},
        {"type": "item.started", "item": {"type": "command_execution", "command": "secret command"}},
        {"type": "item.started", "item": {"type": "mcp_tool_call", "arguments": {"secret": "value"}}},
        {"type": "item.completed", "item": {"type": "command_execution"}},
        {"type": "turn.completed", "usage": {"input_tokens": 111, "output_tokens": 22}},
    ])
    assert observe_agent_jsonl(events) == {
        "completed": True,
        "tool_calls": 2,
        "observed_input_tokens": 111,
        "output_tokens": 22,
    }


def test_agent_observer_ignores_malformed_or_non_tool_events():
    assert observe_agent_jsonl("not-json\n" + json.dumps({"type": "item.started", "item": {"type": "file_change"}})) == {
        "completed": False,
        "tool_calls": 0,
        "observed_input_tokens": None,
        "output_tokens": None,
    }
