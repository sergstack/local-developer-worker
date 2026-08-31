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
