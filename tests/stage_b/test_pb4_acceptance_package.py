from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from local_developer_worker.log_process import log_process
from local_developer_worker.stage_b_accounting import final_accounting, initial_dispositions, validate_v2_candidate
from local_developer_worker.tools import parse_log


ROOT = Path(__file__).parents[2]


def _policy(**semantic):
    return {"automatic": {"semantic_log_clustering": True}, "semantic": {"enabled": True, "code_artifact": "disabled", "model": "qwen3.5:9b", "endpoint": "http://127.0.0.1:11434/api/generate", "routing_event_threshold": 1, **semantic}, "limits": {"timeout_seconds": 60}}


def _event(event_id, *, component="generic", state="parsed", level="error", message="ERROR failure", **extra):
    return {"event_id": event_id, "component": component, "parse_status": state, "level": level, "message": message, **extra}


def test_frozen_corpus_hashes_counts_and_dispositions_are_stable():
    corpus = json.loads((ROOT / "fixtures" / "stage_b" / "pb4_v2_cases.json").read_text())
    for case in corpus["cases"]:
        output = parse_log({"text": case["text"]})
        events = output["data"]["events"]
        actual = {}
        for row in initial_dispositions(events):
            actual.setdefault(row["disposition"], []).append(row["event_id"])
        assert len(events) == case["observed_event_count"]
        assert actual == case["expected_dispositions"]


def test_v2_schema_validates_recorded_contract_candidate():
    schema = json.loads((ROOT / "schemas" / "semantic_grouping_v2.schema.json").read_text())
    candidate = {"contract_version": 2, "groups": [{"group_id": "SG-ONE", "pattern": "failure", "classification": "build_failure", "source_span": ["EV-000001"], "confidence": 0.8, "origin": "model-derived", "needs_review": False}], "ungrouped_candidate_ids": []}
    validate(candidate, schema)


def test_policy_blocked_event_remains_exactly_once_in_final_accounting():
    events = [_event("EV-000001", policy_blocked=True)]
    initial = initial_dispositions(events)
    final, summary = final_accounting(events, initial, [], [], fallback=True)
    assert final[0]["disposition"] == "policy_blocked"
    assert summary["policy_blocked_total"] == 1
    assert summary["fully_accounted"] is True


def test_false_merge_and_generic_catchall_are_rejected():
    events = [_event("EV-000001", component="database"), _event("EV-000002", component="validation")]
    candidate = {"contract_version": 2, "groups": [{"group_id": "SG-ALL", "pattern": "error", "classification": "generic", "source_span": ["EV-000001", "EV-000002"], "confidence": 0.9, "origin": "model-derived", "needs_review": False}], "ungrouped_candidate_ids": []}
    result = validate_v2_candidate(events, candidate, catchall_share=0.5)
    assert result["accepted"] is False
    assert {"catch_all_group", "false_merge_candidate"} <= set(result["errors"])


def test_rollback_smoke_keeps_stage_a_and_full_fallback():
    text = "ERROR first failure\nERROR second failure"
    stage_a = parse_log({"text": text})["data"]["events"]
    calls = []
    bypass = log_process({"text": text, "semantic": False}, _policy(), transport=lambda *args: calls.append(args))
    fallback = log_process({"text": text, "semantic": True}, _policy(), transport=lambda *_: (_ for _ in ()).throw(TimeoutError("probe")))
    assert bypass["data"]["stage_a"]["events"] == stage_a
    assert calls == []
    assert fallback["data"]["fallback_used"] is True
    assert fallback["data"]["accounting"]["fully_accounted"] is True
    assert fallback["data"]["accounting"]["fallback_observed_total"] == 2


def test_code_artifact_policy_remains_blocked_without_transport():
    calls = []
    output = log_process({"text": "ERROR failure", "semantic": True}, _policy(code_artifact="enabled"), transport=lambda *args: calls.append(args))
    assert output["status"] == "policy_blocked"
    assert output["errors"] == [{"code": "semantic_code_artifact_prohibited"}]
    assert calls == []


def test_safe_evaluation_evidence_has_complete_accounting_and_no_raw_response():
    evidence_path = ROOT / "fixtures" / "stage_b" / "pb4_03_evaluation_evidence.json"
    evidence = json.loads(evidence_path.read_text())
    assert evidence["raw_provider_response_stored"] is False
    assert "raw_model_response" not in evidence_path.read_text()
    assert all(row["stage_a_events_match_frozen_input"] is True for rows in evidence["case_results"].values() for row in rows)
    assert evidence["metrics"]["v2"]["fully_accounted_cases"]["value"] == 5
    assert evidence["metrics"]["fallback"]["fallback_coverage"]["value"] == 1.0
    assert evidence["metrics"]["v2"]["invented_accepted_id_count"]["value"] == 0
    assert evidence["metrics"]["v2"]["duplicate_accepted_id_count"]["value"] == 0
    assert evidence["metrics"]["v2"]["omitted_accepted_candidate_id_count"]["value"] == 0
