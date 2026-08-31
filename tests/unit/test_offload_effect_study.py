from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from local_developer_worker.offload_effect_study import analyze_manifest, offload_evaluate, validate_manifest


FIXTURE = Path(__file__).parents[2] / "fixtures" / "offload_effect_study" / "dry_run_manifest.json"
SCHEMAS = Path(__file__).parents[2] / "schemas"


def _manifest() -> dict:
    return json.loads(FIXTURE.read_text())


def test_dry_run_is_exportable_but_never_promoting():
    output = analyze_manifest(_manifest())
    assert output["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert output["promotion_authority"] == "ai_os_only"
    assert output["privacy"]["model_or_provider_invoked"] is False
    assert output["paired_metrics"]["local_compute_burden_ms"] == {"observed_candidate_count": 1, "median_candidate_ms": 550}


def test_observed_live_pairs_are_only_ready_for_ai_os_review():
    manifest = _manifest()
    manifest["mode"] = "live"
    manifest["evidence_status"] = "observed"
    for number in range(2, 4):
        pair = copy.deepcopy(manifest["pairs"][0])
        pair["match_id"] = f"MATCH_{number:03d}"
        manifest["pairs"].append(pair)
    output = analyze_manifest(manifest)
    assert output["verdict"] == "READY_FOR_AI_OS_REVIEW"
    assert output["review_status"] == "EVIDENCE_EXPORT_READY"
    assert output["evidence_export"]["matched_task_ids"] == ["MATCH_001", "MATCH_002", "MATCH_003"]


def test_gold_false_accept_and_reject_stop_review():
    manifest = _manifest()
    manifest["mode"] = "live"
    manifest["evidence_status"] = "observed"
    pair = manifest["pairs"][0]
    pair["gold_accepted"] = False
    pair["candidate"]["accepted"] = True
    output = analyze_manifest(manifest)
    assert output["verdict"] == "STOP"
    assert output["safety"]["false_accept_count"]["candidate"] == 1


def test_manifest_rejects_raw_task_text_and_duplicate_match_ids():
    manifest = _manifest()
    manifest["pairs"][0]["task"] = "never retain real task text"
    with pytest.raises(ValueError, match="invalid_offload_study_pair"):
        validate_manifest(manifest)
    manifest = _manifest()
    manifest["pairs"].append(copy.deepcopy(manifest["pairs"][0]))
    with pytest.raises(ValueError, match="duplicate_match_id"):
        validate_manifest(manifest)


def test_adapter_returns_visible_partial_result_for_synthetic_evidence():
    output = offload_evaluate(_manifest())
    assert output["status"] == "partial"
    assert output["tool"] == "offload_effect_study"


def test_fixture_and_report_conform_to_the_versioned_study_schemas():
    manifest = _manifest()
    input_schema = json.loads((SCHEMAS / "offload_effect_study_input.schema.json").read_text())
    data_schema = json.loads((SCHEMAS / "offload_effect_study_data.schema.json").read_text())
    Draft202012Validator(input_schema).validate(manifest)
    Draft202012Validator(data_schema).validate(analyze_manifest(manifest))


def _matched_arm(**overrides):
    arm = {
        "route": "direct", "profile": "balanced", "terminal_status": "pass",
        "verification_status": "passed", "accepted": True, "wall_clock_ms": 100,
        "provider_input_tokens": 20, "provider_output_tokens": 10, "provider_cost_usd": None,
        "local_compute_ms": None, "initial_context_bytes": None, "cumulative_context_bytes": None,
        "context_expansion_count": 0, "expansion_added_bytes": 0, "compaction_count": 0,
        "reread_after_compaction_count": 0, "agent_tool_calls": 3, "ldw_tool_calls": 0,
        "correction_iterations": 0, "preliminary_attempt_count": 0, "fallback_count": 0,
        "escalation_count": 0, "failure_codes": ["DIRECT_PATH_SUFFICIENT"],
        "policy_revision": None,
    }
    arm.update(overrides)
    return arm


def _matched_manifest():
    pair = {
        "match_id": "MATCH_101", "task_class": "bounded_change_or_debug",
        "acceptance_source": "verifier", "gold_accepted": None,
        "environment_revision": "REVISION_001", "budget": 100, "timeout_ms": 1000,
        "verifier_id": "VERIFIER_001", "acceptance_contract_id": "ACCEPTANCE_001",
        "arm_order": "control_first", "control": _matched_arm(),
        "candidate": _matched_arm(route="deterministic", profile="efficient", wall_clock_ms=80, ldw_tool_calls=2),
    }
    return {
        "contract_version": "1.1.0", "study_id": "OFS_MATCHED_001",
        "sampling_contract_id": "SAMPLE_001", "mode": "live", "evidence_status": "observed",
        "pairs": [pair],
    }


def test_matched_capture_v11_retains_nulls_and_outliers_without_promoting_early():
    manifest = _matched_manifest()
    for number in range(2, 4):
        pair = copy.deepcopy(manifest["pairs"][0])
        pair["match_id"] = f"MATCH_10{number}"
        manifest["pairs"].append(pair)
    output = analyze_manifest(manifest)
    assert output["review_status"] == "EVIDENCE_EXPORT_READY"
    assert output["task_success_regression"] is False
    assert output["paired_metrics"]["provider_cost_usd"] == {"observed_pair_count": 0, "median_delta_percent": None}
    assert output["pair_outcomes"][0]["routes"]["candidate"] == "deterministic"


def test_matched_capture_v11_stops_on_candidate_task_success_regression():
    manifest = _matched_manifest()
    manifest["pairs"][0]["candidate"]["accepted"] = False
    output = analyze_manifest(manifest)
    assert output["verdict"] == "STOP"
    assert output["review_status"] == "TASK_SUCCESS_REGRESSION"


def test_matched_capture_v11_stops_on_gold_acceptance_disagreement():
    manifest = _matched_manifest()
    manifest["pairs"][0]["acceptance_source"] = "gold"
    manifest["pairs"][0]["gold_accepted"] = False
    output = analyze_manifest(manifest)
    assert output["verdict"] == "STOP"
    assert output["review_status"] == "GOLD_ACCEPTANCE_DISAGREEMENT"
    assert output["gold_acceptance_disagreement_count"] == 2


def test_matched_capture_v11_keeps_missing_measurements_visible_and_rejects_unknown_reasons():
    manifest = _matched_manifest()
    for number in range(2, 4):
        pair = copy.deepcopy(manifest["pairs"][0])
        pair["match_id"] = f"MATCH_10{number}"
        manifest["pairs"].append(pair)
    manifest["pairs"][0]["candidate"]["agent_tool_calls"] = None
    output = analyze_manifest(manifest)
    assert output["review_status"] == "MEASUREMENT_INCOMPLETE"
    assert output["measurement_incomplete"] == [{"match_id": "MATCH_101", "fields": ["agent_tool_calls"]}]
    manifest = _matched_manifest()
    manifest["pairs"][0]["candidate"]["failure_codes"] = ["raw_task_text_forbidden"]
    with pytest.raises(ValueError, match="invalid_matched_failure_codes"):
        validate_manifest(manifest)


def test_matched_capture_v11_conforms_to_versioned_schemas():
    manifest = _matched_manifest()
    input_schema = json.loads((SCHEMAS / "offload_effect_study_input.schema.json").read_text())
    data_schema = json.loads((SCHEMAS / "offload_effect_study_data.schema.json").read_text())
    Draft202012Validator(input_schema).validate(manifest)
    Draft202012Validator(data_schema).validate(analyze_manifest(manifest))
