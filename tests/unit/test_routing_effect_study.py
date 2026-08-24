from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from local_developer_worker.routing_effect_study import analyze_manifest, validate_manifest


FIXTURE = Path(__file__).parents[2] / "fixtures" / "routing_effect_study" / "dry_run_manifest.json"


def _manifest() -> dict:
    return json.loads(FIXTURE.read_text())


def test_dry_run_is_deterministic_and_cannot_promote():
    manifest = _manifest()
    first = analyze_manifest(manifest)
    second = analyze_manifest(manifest)
    assert first == second
    assert first["gate_status"] == "INFORMATIONAL_ONLY"
    assert first["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert first["safety"] == {"critical_recall_min": 1, "sensitive_block_count": 0, "complete_pairs": 12, "total_pairs": 12}


def test_manifest_rejects_raw_task_or_path_fields():
    manifest = _manifest()
    manifest["pairs"][0]["task"] = "never persisted"
    with pytest.raises(ValueError, match="invalid_pair_fields"):
        validate_manifest(manifest)


def test_cached_and_reasoning_tokens_do_not_inflate_canonical_total():
    data = analyze_manifest(_manifest())["paired_metrics"]
    assert data["token_semantics"]["provider_total_tokens"] == "input_tokens + output_tokens"
    assert data["token_semantics"]["cached_input_tokens"] == "subset_of_input_tokens"
    assert data["token_semantics"]["reasoning_tokens"] == "diagnostic_only; inclusion_in_output_unknown"


def test_safety_failure_stops_a_live_study():
    manifest = _manifest()
    manifest["study_mode"] = "live"
    manifest["pairs"][0]["context"]["sensitive_block_count"] = 1
    result = analyze_manifest(manifest)
    assert (result["verdict"], result["gate_status"]) == ("STOP", "BLOCKED")


def test_live_promotion_requires_pre_registered_sample_and_material_benefit():
    manifest = _manifest()
    manifest["study_mode"] = "live"
    source = copy.deepcopy(manifest["pairs"])
    manifest["pairs"] = []
    for number in range(30):
        pair = copy.deepcopy(source[number % len(source)])
        pair["pair_id"] = f"LIVE-{number:03d}"
        pair["snapshot_id"] = f"LIVE-SNAPSHOT-{number:03d}"
        pair["adaptive"]["latency_ms"] = pair["control"]["latency_ms"] * 0.7
        pair["adaptive"]["input_tokens"] = pair["control"]["input_tokens"] * 0.7
        pair["adaptive"]["output_tokens"] = pair["control"]["output_tokens"] * 0.7
        pair["context"]["selected_bytes"] = pair["context"]["candidate_bytes"] * 0.6
        manifest["pairs"].append(pair)
    result = analyze_manifest(manifest)
    assert (result["verdict"], result["gate_status"]) == ("PASS", "PROMOTION_CANDIDATE")
    assert set(result["reasons"]) == {"latency", "provider_total_tokens", "selected_context_bytes"}
