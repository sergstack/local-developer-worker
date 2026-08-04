from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from local_developer_worker.log_process import log_process
from local_developer_worker.policy import root_allowed


ROOT = Path(__file__).parents[2]


def _policy(*, timeout_seconds=60, code_artifact="disabled"):
    return {
        "automatic": {"structured_log_parser": True, "semantic_log_clustering": True},
        "semantic": {
            "enabled": True,
            "code_artifact": code_artifact,
            "model": "qwen3:4b",
            "endpoint": "http://127.0.0.1:11435/api/generate",
            "routing_event_threshold": 8,
            "automatic_routing": False,
        },
        "limits": {"timeout_seconds": timeout_seconds},
        "security": {"allowed_repository_roots": []},
    }


def _repeated_log() -> str:
    return "\n".join(["ERROR database connection failed"] * 2)


def _v2_candidate(source_span, *, group_id="SG-ONE", pattern="failure", classification="failure"):
    return {
        "contract_version": 2,
        "groups": [{
            "group_id": group_id,
            "pattern": pattern,
            "classification": classification,
            "source_span": list(source_span),
            "confidence": 0.9,
            "origin": "model-derived",
            "needs_review": False,
        }],
        "ungrouped_candidate_ids": [],
    }


def test_short_log_bypasses_semantic_processing():
    calls = []
    output = log_process({"text": "ERROR one failure"}, _policy(), transport=lambda *args: calls.append(args))

    assert output["data"]["semantic_attempted"] is False
    assert output["data"]["semantic_accepted"] is False
    assert output["data"]["fallback_used"] is False
    assert calls == []

    explicit = log_process(
        {"text": "ERROR one failure", "semantic": True}, _policy(),
        transport=lambda *_: _v2_candidate(["EV-000001"], pattern="one failure", classification="single_failure"),
    )
    assert explicit["data"]["semantic_attempted"] is True
    assert explicit["data"]["semantic_accepted"] is True


def test_explicit_request_attempts_and_accepts_candidate_groups():
    def transport(_endpoint, _request):
        return {
            **_v2_candidate(
                ["EV-000001", "EV-000002"],
                group_id="SG-DB",
                pattern="database connection failed",
                classification="database",
            ),
            "raw_provider_response": "MUST-NOT-ESCAPE",
        }

    output = log_process({"text": _repeated_log(), "semantic": True}, _policy(), transport=transport)

    assert output["status"] == "success"
    assert output["data"]["semantic_attempted"] is True
    assert output["data"]["semantic_accepted"] is True
    assert output["data"]["semantic_groups"][0]["origin"] == "model-derived"
    accounting = output["data"]["final_dispositions"]
    assert [row["event_id"] for row in accounting] == ["EV-000001", "EV-000002"]
    assert len({row["event_id"] for row in accounting}) == len(accounting)
    assert "MUST-NOT-ESCAPE" not in str(output)


def test_invalid_candidate_model_unavailable_and_timeout_fall_back_without_evidence_loss():
    invalid = log_process({"text": _repeated_log(), "semantic": True}, _policy(), transport=lambda *_: {"groups": [], "excluded": []})
    unavailable = log_process({"text": _repeated_log(), "semantic": True}, _policy(), transport=lambda *_: (_ for _ in ()).throw(TimeoutError("raw provider response")))
    timeout = log_process({"text": _repeated_log(), "semantic": True}, _policy(timeout_seconds=0))

    for output in (invalid, unavailable, timeout):
        assert output["status"] == "partial"
        assert output["data"]["fallback_used"] is True
        assert output["data"]["semantic_groups"] == []
        assert len(output["data"]["observed_events"]) == 2
        assert "raw provider response" not in str(output)


def test_unknown_stage_a_events_are_bounded_candidates_and_explicit_false_bypasses():
    calls = []
    invalid = log_process({"text": "unstructured output", "semantic": True}, _policy(), transport=lambda *args: calls.append(args))
    bypassed = log_process({"text": "\n".join(["ERROR failure"] * 8), "semantic": False}, _policy(), transport=lambda *args: calls.append(args))

    assert invalid["data"]["semantic_attempted"] is True
    assert invalid["data"]["fallback_used"] is True
    assert invalid["data"]["model_candidate_events"][0]["parse_status"] == "unknown_event"
    assert bypassed["data"]["semantic_attempted"] is False
    assert len(calls) == 1


def test_non_loopback_and_code_artifact_are_blocked_without_transport():
    calls = []
    policy = _policy()
    policy["semantic"]["endpoint"] = "http://203.0.113.20:11435/api/generate"
    external = log_process({"text": _repeated_log(), "semantic": True}, policy, transport=lambda *args: calls.append(args))
    artifact = log_process({"text": _repeated_log(), "semantic": True}, _policy(code_artifact="enabled"), transport=lambda *args: calls.append(args))

    assert external["status"] == "policy_blocked"
    assert artifact["status"] == "policy_blocked"
    assert calls == []


def test_balanced_global_policy_requires_explicit_repository_root(tmp_path):
    with (ROOT / "examples" / "policies" / "balanced.toml").open("rb") as handle:
        policy = tomllib.load(handle)

    assert policy["automatic"]["semantic_log_clustering"] is True
    assert policy["semantic"]["enabled"] is True
    assert policy["semantic"]["code_artifact"] == "disabled"
    assert policy["semantic"]["automatic_routing"] is False
    assert root_allowed(policy, str(tmp_path), ROOT) is False

    completed = subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", "log", "process"],
        input=json.dumps({"text": "ERROR one failure"}), text=True, capture_output=True, cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "LDW_TELEMETRY_DISABLED": "1"}, check=False,
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["data"]["semantic_attempted"] is False


def test_log_process_enforces_raw_input_size_limit(tmp_path):
    policy_path = tmp_path / "size-limit.toml"
    policy_path.write_text(
        "[automatic]\nstructured_log_parser = true\n"
        "[limits]\nmax_log_size_mb = 0\ntimeout_seconds = 60\n"
        "[fallback]\non_policy_violation = 'codex'\n"
    )
    completed = subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", "log", "process"],
        input=json.dumps({"text": "ERROR oversized", "policy_path": str(policy_path)}),
        text=True,
        capture_output=True,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "LDW_TELEMETRY_DISABLED": "1"},
        check=False,
    )
    output = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert output["status"] == "policy_blocked"
    assert output["errors"] == [{"code": "input_size_exceeded", "limit_bytes": 0}]
