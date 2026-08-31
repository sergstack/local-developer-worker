from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from local_developer_worker.contracts import result
from local_developer_worker.offload_executor import offload_execute


REVISION = "a" * 64


def _payload(**updates):
    payload = {
        "task": "Classify the bounded input",
        "task_class": "bounded_text_classification",
        "risk_floor": "balanced",
        "offload_mode": "local_first",
        "verification_kind": "execution",
        "fallback_policy": {"deterministic": "skip", "frontier": "forbidden"},
        "policy_revision": REVISION,
    }
    payload.update(updates)
    return payload


def _policy(*, local=True, allowed_root="."):
    return {
        "automatic": {"ollama_readonly_advisory": local},
        "ollama": {"enabled": local},
        "security": {"allowed_repository_roots": [allowed_root]},
    }


def _local_success(payload, policy):
    return result(
        "ollama_advisory", "stdin", "{}",
        {
            "terminal_status": "pass", "advisory_status": "accepted",
            "local_runtime_state": "available", "local_model_state": "available",
            "advice": {"summary": "candidate", "next_actions": []},
        },
    )


def _local_unavailable(payload, policy):
    return result(
        "ollama_advisory", "stdin", "{}",
        {"local_runtime_state": "unavailable", "local_model_state": "unknown"},
        status="partial", errors=[{"code": "ollama_runtime_unavailable"}],
    )


def test_local_candidate_preserves_caller_policy_without_gaining_authority():
    payload = _payload()
    output = offload_execute(payload, _policy(), local_executor=_local_success)

    assert output["status"] == "success"
    assert output["data"]["selected_route"] == "local"
    assert output["data"]["authority_status"] == "candidate_only"
    assert output["data"]["task_class"] == "bounded_text_classification"
    assert output["data"]["risk_floor"] == "balanced"
    assert output["data"]["policy_revision"] == REVISION
    assert output["data"]["candidate_provenance"]["source"] == "local_model"
    assert output["data"]["candidate"] == {"summary": "candidate", "next_actions": []}
    schema = json.loads((Path(__file__).parents[2] / "schemas" / "offload_execution_data.schema.json").read_text())
    validate(output["data"], schema)
    input_schema = json.loads((Path(__file__).parents[2] / "schemas" / "offload_execution_input.schema.json").read_text())
    validate(payload, input_schema)


def test_policy_blocked_mode_does_not_invoke_any_executor():
    calls = []
    output = offload_execute(
        _payload(offload_mode="blocked"), _policy(),
        local_executor=lambda *args: calls.append("local"),
        frontier_executor=lambda *args: calls.append("frontier"),
    )

    assert output["status"] == "policy_blocked"
    assert output["errors"] == [{"code": "offload_policy_blocked"}]
    assert calls == []


def test_local_unavailable_uses_observed_deterministic_result_first():
    deterministic = result("test_result_parser", "stdin", "observed", {"run_status": "passed"})
    output = offload_execute(
        _payload(
            fallback_policy={"deterministic": "use_if_available", "frontier": "allowed"},
            deterministic_result=deterministic,
        ),
        _policy(), local_executor=_local_unavailable,
        frontier_executor=lambda *args: (_ for _ in ()).throw(AssertionError("frontier must not run")),
    )

    assert output["status"] == "success"
    assert output["data"]["selected_route"] == "deterministic"
    assert output["data"]["fallback_used"] is True
    assert output["data"]["deterministic_result_ref"]["run_id"] == deterministic["run_id"]


def test_local_unavailable_uses_authorized_frontier_and_preserves_envelope(tmp_path):
    seen = {}

    def frontier(payload, policy):
        seen.update(payload)
        return result("codex_run", "stdin", "{}", {"terminal_status": "pass", "verification_status": "passed"})

    output = offload_execute(
        _payload(
            repository_root=str(tmp_path),
            fallback_policy={"deterministic": "skip", "frontier": "allowed"},
        ),
        _policy(allowed_root=str(tmp_path)), local_executor=_local_unavailable, frontier_executor=frontier,
    )

    assert output["status"] == "success"
    assert output["data"]["selected_route"] == "frontier"
    assert output["data"]["fallback_reason"] == "local_route_unavailable"
    assert output["data"]["task_class"] == "bounded_text_classification"
    assert seen["profile"] == "balanced"
    assert seen["verification"] == {"kind": "execution"}


def test_local_unavailable_and_frontier_forbidden_fails_visibly():
    output = offload_execute(_payload(), _policy(), local_executor=_local_unavailable)

    assert output["status"] == "policy_blocked"
    assert output["data"]["local_capability"] == {"runtime": "unavailable", "model": "unknown"}
    assert output["errors"] == [{"code": "frontier_fallback_forbidden"}]


def test_frontier_floor_skips_local_and_requires_allowed_root(tmp_path):
    calls = []
    output = offload_execute(
        _payload(
            offload_mode="frontier_floor",
            repository_root=str(tmp_path),
            fallback_policy={"deterministic": "skip", "frontier": "allowed"},
        ),
        _policy(allowed_root=str(tmp_path)),
        local_executor=lambda *args: calls.append("local"),
        frontier_executor=lambda payload, policy: result(
            "codex_run", "stdin", "{}", {"terminal_status": "pass", "verification_status": "passed"}
        ),
    )

    assert output["status"] == "success"
    assert output["data"]["selected_route"] == "frontier"
    assert output["data"]["fallback_used"] is False
    assert calls == []


def test_invalid_policy_envelope_is_rejected_before_execution():
    output = offload_execute(_payload(policy_revision="latest"), _policy())

    assert output["status"] == "invalid_input"
    assert output["errors"] == [{"code": "invalid_offload_policy_revision"}]


def test_model_result_cannot_masquerade_as_deterministic_fallback():
    semantic = result("ollama_advisory", "stdin", "{}", {"advisory_status": "accepted"})
    output = offload_execute(_payload(deterministic_result=semantic), _policy())

    assert output["status"] == "invalid_input"
    assert output["errors"] == [{"code": "invalid_deterministic_result"}]
