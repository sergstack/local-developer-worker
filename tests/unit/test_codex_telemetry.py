from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from local_developer_worker.telemetry import CODEX_RUN_FIELDS, codex_run_event, valid_codex_run_event


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


def test_codex_telemetry_has_exact_privacy_allowlist():
    values = {**_values(), "task": "secret prompt", "thread_id": "secret", "provider_response": "secret source"}
    event = codex_run_event(values)
    assert set(event) == CODEX_RUN_FIELDS
    assert valid_codex_run_event(event)
    assert "secret" not in json.dumps(event)


def test_codex_schemas_accept_representative_fixtures():
    repo_root = Path(__file__).parents[2]
    input_fixture = {"task": "Review docs", "repository_root": str(repo_root), "verification": {"kind": "execution"}}
    event = codex_run_event(_values())
    validate(input_fixture, json.loads((repo_root / "schemas/codex_run_input.schema.json").read_text()))
    validate(event, json.loads((repo_root / "schemas/codex_run_event_v1.schema.json").read_text()))
