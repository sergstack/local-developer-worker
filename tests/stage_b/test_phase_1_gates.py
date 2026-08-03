import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import validate

from local_developer_worker.stage_b_gate import (
    INFERENCE_EVENT_FIELDS,
    build_inference_payload,
    evaluate_candidate_response,
    validate_candidate_response,
)
from local_developer_worker.tools import parse_tests

ROOT = Path(__file__).parents[2]
BASE_COMMIT = "5a3d14654e55c51a60439d1478a227cf1fe5a77b"


def _fixtures():
    fixture_root = ROOT / "fixtures" / "stage_b"
    events = json.loads((fixture_root / "reference_events.json").read_text())["events"]
    truth = json.loads((fixture_root / "expected_groups.json").read_text())
    return events, truth


def _candidate(truth):
    return {
        "groups": [
            {
                "group_id": f"SG-{group['group_id'].removeprefix('GT-')}",
                "pattern": group["classification"].replace("_", " "),
                "classification": group["classification"],
                "source_span": group["members"],
                "confidence": 0.8,
                "origin": "model-derived",
                "needs_review": False,
            }
            for group in truth["groups"]
        ],
        "excluded": truth["excluded"],
    }


def test_ref_01_contains_sanitized_reference_corpus_and_ground_truth():
    events, truth = _fixtures()
    accounted = {event_id for group in truth["groups"] for event_id in group["members"]}
    accounted.update(row["event_id"] for row in truth["excluded"])

    assert len(events) >= 30
    assert accounted == {event["event_id"] for event in events}
    assert all(event["origin"] == "observed" for event in events)


def test_gate_01_source_span_recall_accounts_for_every_reference_event():
    events, truth = _fixtures()
    result = validate_candidate_response(events, _candidate(truth), ground_truth=truth)

    assert result["accepted"] is True
    assert result["errors"] == []


def test_gate_01_unaccounted_source_requires_an_explicit_exclusion():
    events, truth = _fixtures()
    candidate = _candidate(truth)
    candidate["excluded"].pop()

    result = validate_candidate_response(events, candidate, ground_truth=truth)

    assert result["accepted"] is False
    assert "source_span_recall_failed" in result["errors"]


def test_gate_02_invented_source_is_rejected_before_output():
    events, truth = _fixtures()
    candidate = _candidate(truth)
    candidate["groups"][0]["source_span"].append("EV-999999")

    result = validate_candidate_response(events, candidate, ground_truth=truth)

    assert result["accepted"] is False
    assert "invented_source" in result["errors"]
    assert result["groups"] == []


@pytest.mark.parametrize("failure", ["timeout", "invalid_model_response"])
def test_gate_03_timeout_or_invalid_response_falls_back_to_observed_events(failure):
    events, _ = _fixtures()

    result = evaluate_candidate_response(events, None, failure=failure)

    assert result["status"] == "partial"
    assert result["fallback_used"] is True
    assert result["semantic_groups"] == []
    assert [event["event_id"] for event in result["observed_events"]] == [event["event_id"] for event in events]
    assert all(event["origin"] == "observed" for event in result["observed_events"])


def test_gate_04_payload_contains_only_log_event_schema_fields():
    events, _ = _fixtures()
    schema = json.loads((ROOT / "schemas" / "log_event.schema.json").read_text())

    payload = build_inference_payload([{**event, "untrusted_extra": "must not leave process"} for event in events])

    assert payload["events"]
    assert all(set(event) <= set(schema["properties"]) == set(INFERENCE_EVENT_FIELDS) for event in payload["events"])
    assert all(event["origin"] == "observed" for event in payload["events"])


def test_gate_04_sensitive_event_is_rejected_before_payload_creation():
    events, _ = _fixtures()
    events[0] = {**events[0], "message": "token=synthetic-sensitive-value"}

    with pytest.raises(ValueError, match="sensitive_event_content"):
        build_inference_payload(events)


def test_gate_05_semantic_groups_are_model_derived_and_observed_events_stay_observed():
    events, truth = _fixtures()
    result = evaluate_candidate_response(events, _candidate(truth), ground_truth=truth)
    schema = json.loads((ROOT / "schemas" / "semantic_group.schema.json").read_text())

    assert result["status"] == "success"
    assert all(event["origin"] == "observed" for event in result["observed_events"])
    for group in result["semantic_groups"]:
        validate(group, schema)
        assert group["origin"] == "model-derived"


def test_gate_05_candidate_without_model_derived_origin_is_rejected():
    events, truth = _fixtures()
    candidate = _candidate(truth)
    candidate["groups"][0]["origin"] = "observed"

    result = validate_candidate_response(events, candidate, ground_truth=truth)

    assert result["accepted"] is False
    assert "invalid_origin" in result["errors"]


def test_gate_05_malformed_semantic_group_contract_is_rejected():
    events, truth = _fixtures()
    candidate = _candidate(truth)
    candidate["groups"][0]["needs_review"] = "false"

    result = validate_candidate_response(events, candidate, ground_truth=truth)

    assert result["accepted"] is False
    assert "invalid_group_contract" in result["errors"]


@pytest.mark.parametrize("confidence", [-0.01, 1.01, True, "0.9"])
def test_gate_06_confidence_outside_numeric_bounds_is_rejected(confidence):
    events, truth = _fixtures()
    candidate = _candidate(truth)
    candidate["groups"][0]["confidence"] = confidence

    result = validate_candidate_response(events, candidate, ground_truth=truth)

    assert result["accepted"] is False
    assert "confidence_out_of_bounds" in result["errors"]


def test_nr_01_path_disagreement_forces_review_independent_of_confidence():
    event = {
        "event_id": "EV-900001",
        "level": "error",
        "component": "shell",
        "message": "deployment command failed",
        "exception_type": None,
        "source_file": "scripts/deploy_prod.sh",
        "source_line": 1,
        "raw_line_start": 1,
        "raw_line_end": 1,
        "raw_hash": "0" * 64,
        "parse_status": "parsed",
        "origin": "observed",
    }
    candidate = {
        "groups": [{
            "group_id": "SG-DEPLOY",
            "pattern": "documentation update",
            "classification": "documentation",
            "source_span": ["EV-900001"],
            "confidence": 1.0,
            "origin": "model-derived",
            "needs_review": False,
        }],
        "excluded": [],
    }

    result = validate_candidate_response([event], candidate)

    assert result["accepted"] is True
    assert result["groups"][0]["needs_review"] is True


def test_gate_07_stage_a_safety_matrix_is_unchanged_and_passes_via_test_parser():
    relative = "tests/integration/test_stage_a_safety_matrix.py"
    baseline = subprocess.run(
        ["git", "show", f"{BASE_COMMIT}:{relative}"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    assert (ROOT / relative).read_bytes() == baseline

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rA", relative],
        cwd=ROOT,
        env={**os.environ, "LDW_TELEMETRY_DISABLED": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    parsed = parse_tests({
        "text": completed.stdout + completed.stderr,
        "exit_code": completed.returncode,
        "command_observed": True,
        "source": "stage-a-safety-matrix",
    })

    assert parsed["data"]["run_status"] == "passed"
    assert parsed["data"]["tests"]
