from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from local_developer_worker.telemetry import CODEX_ROUTING_V2_FIELDS, CODEX_RUN_FIELDS, codex_routing_event_v2, codex_run_event, valid_codex_routing_event_v2, valid_codex_run_event


def _values():
    return {
        "run_id": "RUN-safe",
        "profile": "balanced",
        "model_alias": "standard",
        "effort": "medium",
        "terminal_status": "pass",
        "verification_status": "passed",
        "fallback_count": 0,
        "escalation_count": 0,
        "input_tokens": 10,
        "cached_input_tokens": None,
        "output_tokens": 2,
        "reasoning_output_tokens": 1,
    }


def _routing_values():
    return {
        "run_id": "RUN-routing-safe", "base_task_class": "routine_read_or_docs", "routing_signal": "text:read",
        "routing_disposition": "adaptive", "override_requested_profile": None, "override_state": "none", "adaptive_routing": True,
        "calibration_eligible": True,
        "deterministic_risk_floor": "efficient", "initial_profile": "efficient", "initial_effort": "low",
        "final_profile": "efficient", "final_effort": "low", "fallback_count": 0, "escalation_count": 0,
        "first_pass_verification_status": "passed", "final_verification_status": "passed", "terminal_status": "pass",
        "input_tokens": 10, "cached_input_tokens": None, "output_tokens": 2, "reasoning_output_tokens": 1,
        "latency_ms": 12, "policy_revision": "a" * 64, "routing_revision": "b" * 64,
        "alias_revision": "c" * 64, "taxonomy_revision": "d" * 64,
    }


def test_codex_telemetry_has_exact_privacy_allowlist():
    values = {**_values(), "task": "secret prompt", "thread_id": "secret", "provider_response": "secret source"}
    event = codex_run_event(values)
    assert set(event) == CODEX_RUN_FIELDS
    assert valid_codex_run_event(event)
    assert "secret" not in json.dumps(event)


def test_calibration_telemetry_has_exact_privacy_allowlist_and_versioned_schema():
    values = {**_routing_values(), "task": "secret prompt", "path": "/private/source.py", "thread_id": "secret", "provider_response": "secret"}
    event = codex_routing_event_v2(values)
    assert set(event) == CODEX_ROUTING_V2_FIELDS
    assert valid_codex_routing_event_v2(event)
    assert "secret" not in json.dumps(event)


def test_codex_schemas_accept_representative_fixtures():
    repo_root = Path(__file__).parents[2]
    input_fixture = {"task": "Review docs", "repository_root": str(repo_root), "verification": {"kind": "execution"}}
    event = codex_run_event(_values())
    routing_event = codex_routing_event_v2(_routing_values())
    validate(input_fixture, json.loads((repo_root / "schemas/codex_run_input.schema.json").read_text()))
    validate(event, json.loads((repo_root / "schemas/codex_run_event_v1.schema.json").read_text()))
    validate(routing_event, json.loads((repo_root / "schemas/codex_routing_event_v2.schema.json").read_text()))


def test_v21_routing_records_remain_readable_and_schema_valid():
    repo_root = Path(__file__).parents[2]
    values = _routing_values()
    legacy = {
        **{key: value for key, value in codex_routing_event_v2(values).items() if key not in {"base_task_class", "routing_disposition", "override_requested_profile", "override_state", "adaptive_routing", "calibration_eligible"}},
        "schema_version": "2.1.0",
        "task_class": values["base_task_class"],
    }
    assert valid_codex_routing_event_v2(legacy)
    validate(legacy, json.loads((repo_root / "schemas/codex_routing_event_v2.schema.json").read_text()))


def test_v22_routing_records_remain_readable_and_schema_valid():
    repo_root = Path(__file__).parents[2]
    current = codex_routing_event_v2(_routing_values())
    legacy = {key: value for key, value in current.items() if key != "calibration_eligible"}
    legacy["schema_version"] = "2.2.0"
    assert valid_codex_routing_event_v2(legacy)
    validate(legacy, json.loads((repo_root / "schemas/codex_routing_event_v2.schema.json").read_text()))
