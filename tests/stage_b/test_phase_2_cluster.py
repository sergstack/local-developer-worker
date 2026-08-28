from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from jsonschema import validate

from local_developer_worker.contracts import canonical_json
from local_developer_worker.stage_b_cluster import log_cluster


ROOT = Path(__file__).parents[2]
TOOL_RESULT_SCHEMA = json.loads((ROOT / "schemas" / "tool_result.schema.json").read_text())
SEMANTIC_CLUSTER_SCHEMA = json.loads((ROOT / "schemas" / "semantic_cluster_result.schema.json").read_text())


def _events_and_candidate():
    fixture_root = ROOT / "fixtures" / "stage_b"
    events = json.loads((fixture_root / "reference_events.json").read_text())["events"]
    truth = json.loads((fixture_root / "expected_groups.json").read_text())
    candidate = {
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
    return events, candidate


def _enabled_policy(*, endpoint="http://127.0.0.1:11435/api/generate", code_artifact="disabled"):
    return {
        "automatic": {"semantic_log_clustering": True},
        "semantic": {
            "enabled": True,
            "code_artifact": code_artifact,
            "model": "qwen3:4b",
            "endpoint": endpoint,
        },
        "limits": {"timeout_seconds": 60},
    }


def _run_cli(payload):
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "LDW_TELEMETRY_DISABLED": "1"}
    environment.pop("LDW_POLICY_PATH", None)
    return subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", "log", "cluster"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=ROOT,
        env=environment,
        check=False,
    )


def test_pb2_03_default_policy_blocks_semantic_dispatch():
    completed = _run_cli({"events": []})
    output = json.loads(completed.stdout)

    assert completed.returncode == 2
    assert output["status"] == "policy_blocked"
    assert output["errors"] == [{"code": "semantic_disabled"}]
    validate(output, TOOL_RESULT_SCHEMA)


def test_pb2_03_rejects_non_parsed_event_shape_before_model_dispatch():
    events, _ = _events_and_candidate()
    invalid = [{key: value for key, value in events[0].items() if key != "raw_hash"}]
    calls = []

    output = log_cluster(
        {"events": invalid},
        _enabled_policy(),
        transport=lambda endpoint, body: calls.append((endpoint, body)),
    )

    assert output["status"] == "invalid_input"
    assert output["errors"] == [{"code": "parsed_log_events_required"}]
    assert calls == []


def test_pb2_03_rejects_empty_event_set_before_model_dispatch():
    calls = []

    output = log_cluster(
        {"events": []},
        _enabled_policy(),
        transport=lambda endpoint, body: calls.append((endpoint, body)),
    )

    assert output["status"] == "invalid_input"
    assert output["errors"] == [{"code": "parsed_log_events_required"}]
    assert calls == []


def test_pb2_03_pipeline_uses_policy_config_and_existing_gate_functions():
    events, candidate = _events_and_candidate()
    supplied_events = [{**event, "untrusted_extra": "MUST-NOT-LEAVE"} for event in events]
    calls = []

    def transport(endpoint, request_payload):
        calls.append((endpoint, request_payload))
        return {**candidate, "raw_response": "MUST-NOT-ESCAPE"}

    output = log_cluster(
        {"events": supplied_events, "model": "payload-model", "endpoint": "http://example.invalid"},
        _enabled_policy(),
        transport=transport,
    )

    assert output["status"] == "success"
    assert output["data"]["fallback_used"] is False
    assert output["data"]["model"] == "qwen3:4b"
    assert len(calls) == 1
    assert calls[0][0] == "http://127.0.0.1:11435/api/generate"
    assert calls[0][1]["model"] == "qwen3:4b"
    assert "MUST-NOT-LEAVE" not in calls[0][1]["prompt"]
    assert "MUST-NOT-LEAVE" not in canonical_json(output)
    assert "MUST-NOT-ESCAPE" not in canonical_json(output)
    assert all(group["origin"] == "model-derived" for group in output["data"]["semantic_groups"])
    validate(output, TOOL_RESULT_SCHEMA)
    validate(output["data"], SEMANTIC_CLUSTER_SCHEMA)


def test_pb2_03_non_loopback_endpoint_is_blocked_before_transport():
    events, _ = _events_and_candidate()
    calls = []

    output = log_cluster(
        {"events": events},
        _enabled_policy(endpoint="http://203.0.113.20:11435/api/generate"),
        transport=lambda endpoint, body: calls.append((endpoint, body)),
    )

    assert output["status"] == "policy_blocked"
    assert output["errors"] == [{"code": "non_loopback_inference_endpoint"}]
    assert calls == []


def test_pb4_04_production_path_rejects_loopback_ssh_listener_before_transport(monkeypatch):
    events, _ = _events_and_candidate()
    calls = []

    def process_probe(command, **_kwargs):
        if command[0] == "lsof":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="ssh 44001 user 10u IPv4 0t0 TCP 127.0.0.1:11435 (LISTEN)\n",
                stderr="",
            )
        raise AssertionError("process inspection must stop after identifying the tunnel")

    monkeypatch.setattr("local_developer_worker.policy._PROCESS_RUNNER", process_probe)
    monkeypatch.setattr(
        "local_developer_worker.stage_b_cluster.ollama_transport",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    output = log_cluster({"events": events}, _enabled_policy())

    assert output["status"] == "policy_blocked"
    assert output["errors"] == [{"code": "local_inference_runtime_unverified"}]
    assert calls == []


def test_pb4_04_custom_transport_cannot_skip_unverified_runtime(monkeypatch):
    events, candidate = _events_and_candidate()
    calls = []

    def unavailable_listener(command, **_kwargs):
        assert command[0] == "lsof"
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="")

    def transport(endpoint, request_payload):
        calls.append((endpoint, request_payload))
        return candidate

    monkeypatch.setattr("local_developer_worker.policy._PROCESS_RUNNER", unavailable_listener)

    output = log_cluster({"events": events}, _enabled_policy(), transport=transport)

    assert output["status"] == "policy_blocked"
    assert output["errors"] == [{"code": "local_inference_runtime_unverified"}]
    assert calls == []


def test_pb2_03_transport_failure_returns_honest_observed_fallback():
    events, _ = _events_and_candidate()

    def unavailable(_endpoint, _request_payload):
        raise TimeoutError("synthetic detail must not escape")

    output = log_cluster({"events": events}, _enabled_policy(), transport=unavailable)

    assert output["status"] == "partial"
    assert output["data"]["fallback_used"] is True
    assert output["data"]["fallback_reason"] == ["model_unavailable"]
    assert output["data"]["semantic_groups"] == []
    assert output["data"]["observed_events"] == events
    assert "synthetic detail" not in canonical_json(output)


def test_pb2_03_code_artifact_is_rejected_before_dispatch(tmp_path):
    policy = tmp_path / "policy.toml"
    policy.write_text(
        """profile = "minimal"
network_access = false
automatic_edit = false
automatic_commit = false
automatic_merge = false
production_deploy = false
[automatic]
semantic_log_clustering = true
[semantic]
enabled = true
code_artifact = "enabled"
model = "qwen3:4b"
endpoint = "http://127.0.0.1:11435/api/generate"
[limits]
timeout_seconds = 60
[fallback]
on_policy_violation = "codex"
"""
    )
    completed = _run_cli({"events": [], "policy_path": str(policy)})
    output = json.loads(completed.stdout)

    assert output["status"] == "policy_blocked"
    assert output["errors"] == [{"code": "semantic_code_artifact_prohibited"}]
