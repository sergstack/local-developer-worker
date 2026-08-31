from __future__ import annotations

from local_developer_worker.ollama_advisor import OllamaModelUnavailable, _NoRedirect, ollama_advise, ollama_capability


def _policy(*, endpoint: str = "http://127.0.0.1:11435/api/generate") -> dict:
    return {"ollama": {"model": "qwen3:8b", "endpoint": endpoint, "timeout_seconds": 5}}


def test_ollama_advisory_blocks_non_loopback_before_transport():
    calls: list[object] = []
    output = ollama_advise(
        {"task": "Review one function"}, _policy(endpoint="http://203.0.113.3/api/generate"),
        transport=lambda *args: calls.append(args),
    )
    assert output["status"] == "policy_blocked"
    assert output["errors"] == [{"code": "non_loopback_inference_endpoint"}]
    assert calls == []


def test_ollama_transport_disables_http_redirects():
    assert _NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://example.invalid") is None


def test_ollama_advisory_never_returns_raw_candidate(monkeypatch):
    def guarded(endpoint, request, transport):
        assert request["model"] == "qwen3:8b"
        assert "Review one function" in request["prompt"]
        return {"status": "success", "data": {"local_runtime_verified": True, "physical_inference_locality": "not_provable"}}, {
            "summary": "Inspect the focused function first.", "next_actions": ["Run its focused tests."], "raw": "must not escape",
        }

    monkeypatch.setattr("local_developer_worker.ollama_advisor.guarded_inference_call", guarded)
    output = ollama_advise({"task": "Review one function"}, _policy())
    assert output["status"] == "partial"
    assert output["data"]["raw_response_retained"] is False
    assert "must not escape" not in str(output)


def test_ollama_advisory_returns_only_validated_structured_advice(monkeypatch):
    monkeypatch.setattr(
        "local_developer_worker.ollama_advisor.guarded_inference_call",
        lambda endpoint, request, transport: (
            {"status": "success", "data": {"local_runtime_verified": True, "physical_inference_locality": "not_provable"}},
            {"summary": "Inspect the focused function first.", "next_actions": ["Run its focused tests."]},
        ),
    )
    output = ollama_advise({"task": "Review one function"}, _policy())
    assert output["status"] == "success"
    assert output["data"]["advisory_status"] == "accepted"
    assert output["data"]["advice"] == {"summary": "Inspect the focused function first.", "next_actions": ["Run its focused tests."]}
    assert output["data"]["raw_response_retained"] is False
    assert output["data"]["local_runtime_state"] == "available"
    assert output["data"]["local_model_state"] == "available"


def test_ollama_advisory_distinguishes_runtime_unavailable(monkeypatch):
    monkeypatch.setattr(
        "local_developer_worker.ollama_advisor.guarded_inference_call",
        lambda endpoint, request, transport: (_ for _ in ()).throw(ConnectionRefusedError()),
    )
    output = ollama_advise({"task": "Review one function"}, _policy())

    assert output["status"] == "partial"
    assert output["data"]["local_runtime_state"] == "unavailable"
    assert output["data"]["local_model_state"] == "unknown"
    assert output["errors"] == [{"code": "ollama_runtime_unavailable"}]


def test_ollama_advisory_distinguishes_requested_model_unavailable(monkeypatch):
    monkeypatch.setattr(
        "local_developer_worker.ollama_advisor.guarded_inference_call",
        lambda endpoint, request, transport: (_ for _ in ()).throw(OllamaModelUnavailable()),
    )
    output = ollama_advise({"task": "Review one function"}, _policy())

    assert output["status"] == "partial"
    assert output["data"]["local_runtime_state"] == "available"
    assert output["data"]["local_model_state"] == "unavailable"
    assert output["errors"] == [{"code": "ollama_model_unavailable"}]


def test_ollama_capability_distinguishes_disabled_missing_model_and_runtime(monkeypatch):
    assert ollama_capability({})["status"] == "policy_blocked"
    policy = {"ollama": {**_policy()["ollama"], "enabled": True}, "automatic": {"ollama_readonly_advisory": True}}
    monkeypatch.setattr("local_developer_worker.ollama_advisor.guarded_inference_call", lambda *args: ({"status": "success", "data": {}}, {"models": []}))
    assert ollama_capability(policy)["status"] == "model_unavailable"
    monkeypatch.setattr("local_developer_worker.ollama_advisor.guarded_inference_call", lambda *args: ({"status": "policy_blocked", "errors": [{"code": "local_inference_runtime_unverified"}]}, None))
    assert ollama_capability(policy)["status"] == "unavailable"
