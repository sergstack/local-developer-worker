from __future__ import annotations

import copy
from datetime import date, timedelta

from local_developer_worker.codex_routing import validate_codex_policy
from local_developer_worker.routing_calibration import routing_calibrate, routing_explain, routing_stats
from local_developer_worker.session_log import append_event
from local_developer_worker.telemetry import codex_routing_event_v2


def _policy(*, enabled: bool = True) -> dict:
    return {
        "network_access": True,
        "codex": {
            "enabled": True, "adaptive_routing": True, "allow_profile_downgrade": False, "allow_write": False,
            "allow_network": True, "default_profile": "balanced", "risk_floor": "efficient", "maximum_profile": "frontier",
            "executable": "/usr/bin/true", "allowed_executables": ["/usr/bin/true"],
            "verification_executables": ["/usr/bin/true"], "verification_commands": [["/usr/bin/true"]],
            "environment_allowlist": ["PATH"], "supported_cli_versions": ["0.147"], "sandbox": "read-only",
            "approval_policy": "never", "max_escalations": 2, "timeout_seconds": 60, "verification_timeout_seconds": 30,
            "max_output_bytes": 100000, "max_task_bytes": 100000, "retriable_error_codes": ["timeout"],
            "profiles": {"efficient": {"alias": "small", "effort": "low"}, "balanced": {"alias": "standard", "effort": "medium"}, "frontier": {"alias": "large", "effort": "high"}},
            "aliases": {"small": {"model": "model-a", "supported_efforts": ["low"], "fallback_aliases": []}, "standard": {"model": "model-b", "supported_efforts": ["medium"], "fallback_aliases": []}, "large": {"model": "model-c", "supported_efforts": ["high"], "fallback_aliases": []}},
            "escalation": {"efficient": "balanced", "balanced": "frontier"},
            "calibration": {"enabled": enabled, "min_samples": 20, "strong_sample": 50, "max_age_days": 90, "under_routing_escalation_rate": 0.35, "under_routing_first_pass_rate": 0.8, "over_routing_first_pass_rate": 0.95},
        },
    }


def _event(number: int, *, task_class: str = "routine_read_or_docs", initial: str = "efficient", final: str | None = None, floor: str | None = None, first: str = "passed", terminal: str = "pass", verification: str = "passed", escalations: int = 0, revisions: dict | None = None) -> dict:
    final = final or initial
    effort = {"efficient": "low", "balanced": "medium", "frontier": "high"}
    revisions = revisions or validate_codex_policy(_policy())
    return codex_routing_event_v2({
        "run_id": f"RUN-cal-{number}", "base_task_class": task_class, "routing_signal": "structured:" + task_class,
        "routing_disposition": "adaptive", "override_requested_profile": None, "override_state": "none", "adaptive_routing": True,
        "deterministic_risk_floor": floor or initial, "initial_profile": initial, "initial_effort": effort[initial],
        "final_profile": final, "final_effort": effort[final], "fallback_count": 0, "escalation_count": escalations,
        "first_pass_verification_status": first, "final_verification_status": verification, "terminal_status": terminal,
        "input_tokens": 10, "cached_input_tokens": 1, "output_tokens": 2, "reasoning_output_tokens": 3,
        "latency_ms": 20 + number, "policy_revision": revisions["policy_revision"], "routing_revision": revisions["routing_revision"],
        "alias_revision": revisions["alias_revision"], "taxonomy_revision": revisions["taxonomy_revision"],
    })


def _append_many(root, rows, *, observed_on: date | None = None):
    for row in rows:
        append_event(row, root, event_date=observed_on or date.today())


def test_stats_aggregate_only_v2_safe_events(tmp_path):
    _append_many(tmp_path, [_event(1), _event(2, escalations=1, final="balanced", first="not_observed")])
    data = routing_stats({"journal_root": str(tmp_path)})["data"]
    assert data["population_analyzed"] == 2
    assert data["task_classes"][0]["sample_size"] == 2
    assert data["task_classes"][0]["escalation_rate"] == 0.5
    assert data["task_classes"][0]["median_tokens_per_verified_task"] == 16


def test_calibration_requires_minimum_evidence_and_never_writes_policy(tmp_path):
    _append_many(tmp_path, [_event(index, escalations=1, final="balanced", first="not_observed") for index in range(1, 20)])
    policy = _policy()
    before = copy.deepcopy(policy)
    output = routing_calibrate({"journal_root": str(tmp_path)}, policy)
    assert output["data"]["verdict"] == "insufficient-evidence"
    assert output["data"]["proposed_changes"] == []
    assert output["data"]["replay"]["counterfactual_outcome"] == "unverified"
    assert policy == before


def test_calibration_detects_under_routing_from_observed_escalation_evidence(tmp_path):
    _append_many(tmp_path, [_event(index, escalations=1 if index <= 8 else 0, final="balanced" if index <= 8 else "efficient", first="not_observed" if index <= 8 else "passed") for index in range(1, 21)])
    output = routing_calibrate({"journal_root": str(tmp_path)}, _policy())
    proposal = output["data"]["detected_under_routing"][0]
    assert output["data"]["verdict"] == "candidate-change"
    assert (proposal["from_profile"], proposal["to_profile"], proposal["confidence"]) == ("efficient", "balanced", "weak")
    assert output["data"]["candidate_revision"]["acceptance_status"] == "pending_human_acceptance"
    assert output["data"]["candidate_revision"]["rollback_target"] == output["data"]["current_policy_revision"]
    assert proposal["supporting_metrics"]["under_routing_rate"] == 0.4
    assert output["data"]["replay"]["comparisons"][0]["counterfactual_outcome"] == "unverified"


def test_calibration_candidate_and_replay_are_deterministic(tmp_path):
    _append_many(tmp_path, [_event(index, escalations=1 if index <= 8 else 0, final="balanced" if index <= 8 else "efficient", first="not_observed" if index <= 8 else "passed") for index in range(1, 21)])
    first = routing_calibrate({"journal_root": str(tmp_path)}, _policy())["data"]
    second = routing_calibrate({"journal_root": str(tmp_path)}, _policy())["data"]
    assert first["candidate_revision"] == second["candidate_revision"]
    assert first["replay"] == second["replay"]


def test_mixed_policy_revisions_are_separated_and_cannot_create_strong_recommendation(tmp_path):
    current = validate_codex_policy(_policy())
    old_policy = _policy()
    old_policy["codex"]["aliases"]["small"]["model"] = "old-model"
    old = validate_codex_policy(old_policy)
    _append_many(tmp_path, [_event(index, escalations=1 if index <= 8 else 0, final="balanced" if index <= 8 else "efficient", first="not_observed" if index <= 8 else "passed", revisions=current) for index in range(1, 21)])
    _append_many(tmp_path, [_event(100 + index, revisions=old) for index in range(1, 51)])
    stats = routing_stats({"journal_root": str(tmp_path)})["data"]
    output = routing_calibrate({"journal_root": str(tmp_path)}, _policy())["data"]
    assert stats["mixed_revision_population"] is True
    assert len(stats["task_classes"]) == 2
    assert output["mixed_revision_population"] is True
    assert output["excluded_incompatible_records"] == 50
    assert output["detected_under_routing"][0]["confidence"] == "weak"


def test_attempt_records_with_one_run_id_count_as_one_independent_task(tmp_path):
    escalation = _event(1, initial="balanced", final="frontier", escalations=1, first="not_observed")
    _append_many(tmp_path, [escalation] * 6)
    _append_many(tmp_path, [_event(index, initial="balanced") for index in range(2, 21)])
    data = routing_stats({"journal_root": str(tmp_path)})["data"]
    group = data["task_classes"][0]
    assert data["population_analyzed"] == 20
    assert data["duplicate_attempt_records"] == 5
    assert group["sample_size"] == 20
    assert group["escalation_rate"] == 0.05


def test_stale_observations_are_excluded_from_calibration_window(tmp_path):
    policy = _policy()
    policy["codex"]["calibration"]["max_age_days"] = 30
    revisions = validate_codex_policy(policy)
    _append_many(tmp_path, [_event(index, escalations=1, final="balanced", first="not_observed", revisions=revisions) for index in range(1, 51)], observed_on=date.today() - timedelta(days=31))
    _append_many(tmp_path, [_event(100 + index, revisions=revisions) for index in range(1, 21)])
    output = routing_calibrate({"journal_root": str(tmp_path)}, policy)["data"]
    assert output["stale_records"] == 50
    assert output["population_analyzed"] == 20
    assert output["detected_under_routing"] == []


def test_calibration_cannot_lower_a_deterministic_risk_floor(tmp_path):
    rows = [_event(index, initial="balanced", floor="balanced") for index in range(1, 21)]
    rows.extend([_event(100 + index, initial="efficient", floor="efficient") for index in range(1, 3)])
    _append_many(tmp_path, rows)
    output = routing_calibrate({"journal_root": str(tmp_path)}, _policy())
    assert output["data"]["detected_over_routing"] == []


def test_calibration_detects_overrouting_only_with_lower_profile_verified_evidence(tmp_path):
    rows = [_event(index, initial="balanced", floor="efficient") for index in range(1, 21)]
    rows.extend([_event(100 + index, initial="efficient", floor="efficient") for index in range(1, 3)])
    _append_many(tmp_path, rows)
    output = routing_calibrate({"journal_root": str(tmp_path)}, _policy())
    proposal = output["data"]["detected_over_routing"][0]
    assert (proposal["from_profile"], proposal["to_profile"], proposal["confidence"]) == ("balanced", "efficient", "weak")
    assert proposal["supporting_metrics"]["over_routing_candidate_rate"] == 1.0


def test_calibration_ignores_failed_or_unverified_as_overrouting_success(tmp_path):
    rows = [_event(index, initial="balanced", first="uncertain", terminal="failed", verification="uncertain") for index in range(1, 21)]
    rows.extend([_event(100 + index, initial="efficient") for index in range(1, 3)])
    _append_many(tmp_path, rows)
    output = routing_calibrate({"journal_root": str(tmp_path)}, _policy())
    assert output["data"]["detected_over_routing"] == []


def test_explain_returns_route_without_concrete_model_or_task(tmp_path):
    output = routing_explain({"task": "Review docs"}, _policy())
    data = output["data"]
    assert data["selected_profile"] == "efficient"
    assert data["effort"] == "low"
    assert "model" not in data
    assert "task" not in data


def test_stats_reports_malformed_telemetry_as_partial_without_using_it(tmp_path):
    (tmp_path / "2026-08-21.jsonl").write_text('{"task":"must-not-be-ingested"}\n', encoding="utf-8")
    output = routing_stats({"journal_root": str(tmp_path)})
    assert output["status"] == "partial"
    assert output["data"]["population_analyzed"] == 0
    assert output["data"]["task_classes"] == []
    assert output["data"]["invalid_records"] == 1
