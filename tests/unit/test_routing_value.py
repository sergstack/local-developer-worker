from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from local_developer_worker.routing_value import routing_value
from local_developer_worker.session_log import append_event
from local_developer_worker.telemetry import codex_routing_event_v2


ROOT = Path(__file__).parents[2]


def _result() -> dict:
    return {
        "schema_version": "1.0.0", "tool": "codex_run", "run_id": "RUN-value", "status": "success",
        "input_manifest": {"source": "stdin", "size_bytes": 1, "sha256": "a" * 64}, "warnings": [], "errors": [], "metrics": {},
        "data": {
            "execution_id": "EXEC-00000000000000000000000000000001", "profile": "efficient", "model_alias": "luna", "effort": "low",
            "routing_signal": "text:read", "routing_confidence": "certain", "deterministic_risk_floor": "efficient", "policy_revision": "a" * 64,
            "terminal_status": "pass", "verification_status": "passed", "fallback_count": 0, "escalation_count": 0,
            "execution_attempted": True, "model_execution_completed": True, "calibration_eligible": True,
            "input_tokens": 100, "cached_input_tokens": 40, "non_cached_input_tokens": 60, "output_tokens": 10,
            "reasoning_output_tokens": 4, "provider_total_tokens": 110, "reasoning_in_output_status": "unknown",
        },
    }


def _event() -> dict:
    return codex_routing_event_v2({
        "run_id": "RUN-value", "execution_id": "EXEC-00000000000000000000000000000001", "base_task_class": "routine_read_or_docs",
        "routing_signal": "text:read", "routing_disposition": "adaptive", "override_requested_profile": None, "override_state": "none", "adaptive_routing": True,
        "calibration_eligible": True, "deterministic_risk_floor": "efficient", "initial_profile": "efficient", "initial_effort": "low",
        "final_profile": "efficient", "final_effort": "low", "fallback_count": 0, "escalation_count": 0,
        "first_pass_verification_status": "passed", "final_verification_status": "passed", "terminal_status": "pass",
        "input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 10, "reasoning_output_tokens": 4, "latency_ms": 123,
        "policy_revision": "a" * 64, "routing_revision": "b" * 64, "alias_revision": "c" * 64, "taxonomy_revision": "d" * 64,
    })


def test_value_reports_one_observed_run_without_counterfactual_claim(tmp_path):
    append_event(_event(), tmp_path)
    output = routing_value({"codex_result": _result(), "journal_root": str(tmp_path)})
    data = output["data"]
    assert output["status"] == "success"
    assert data["observed"]["latency"] == {"status": "observed", "latency_ms": 123}
    assert data["observed"]["tokens"]["provider_total_tokens"] == 110
    assert data["comparison"]["status"] == "not_available"
    assert data["context"]["status"] == "not_measured"
    assert data["quality"]["status"] == "not_measured"
    validate(data, json.loads((ROOT / "schemas/routing_value_data.schema.json").read_text()))


def test_value_does_not_invent_latency_when_no_matching_journal_record(tmp_path):
    output = routing_value({"codex_result": _result(), "journal_root": str(tmp_path)})
    assert output["status"] == "success"
    assert output["data"]["observed"]["latency"] == {"status": "not_measured", "reason": "matching_routing_observation_not_found"}


def test_value_accepts_only_safe_context_metrics(tmp_path):
    append_event(_event(), tmp_path)
    output = routing_value({"codex_result": _result(), "journal_root": str(tmp_path), "context_observation": {"candidate_bytes": 1000, "selected_bytes": 600, "critical_recall": 1.0, "sensitive_block_count": 0}})
    assert output["data"]["context"] == {"status": "observed", "candidate_bytes": 1000, "selected_bytes": 600, "context_reduction": 0.4, "critical_recall": 1.0, "sensitive_block_count": 0}
    unsafe = routing_value({"codex_result": _result(), "context_observation": {"candidate_bytes": 1, "selected_bytes": 1, "critical_recall": 1, "sensitive_block_count": 0, "path": "secret.py"}})
    assert unsafe["status"] == "partial"
    assert unsafe["data"]["context"]["status"] == "not_measured"


def test_value_rejects_non_codex_tool_result():
    invalid = _result()
    invalid["tool"] = "doctor"
    output = routing_value({"codex_result": invalid})
    assert output["status"] == "invalid_input"
