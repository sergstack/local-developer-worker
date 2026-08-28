from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable

from .contracts import canonical_json, result
from .policy import guarded_inference_call


ADVICE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "next_actions"],
    "properties": {
        "summary": {"type": "string", "minLength": 1, "maxLength": 600},
        "next_actions": {
            "type": "array", "maxItems": 5,
            "items": {"type": "string", "minLength": 1, "maxLength": 240},
        },
    },
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Preserve the loopback-only endpoint boundary during the request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _transport(endpoint: str, request_payload: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=canonical_json(request_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _NoRedirect(),
    )
    with opener.open(request, timeout=timeout) as response:
        body = response.read(65_537)
    if len(body) > 65_536:
        raise ValueError("model_response_too_large")
    envelope = json.loads(body)
    answer = json.loads(envelope["response"])
    if not isinstance(answer, dict):
        raise ValueError("invalid_model_response")
    return answer


def _safe_advice(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or set(value) != {"summary", "next_actions"}:
        return None
    summary, actions = value["summary"], value["next_actions"]
    if (
        not isinstance(summary, str)
        or not summary.strip()
        or len(summary) > 600
        or not isinstance(actions, list)
        or len(actions) > 5
        or any(not isinstance(item, str) or not item.strip() or len(item) > 240 for item in actions)
    ):
        return None
    return {"summary": summary.strip(), "next_actions": [item.strip() for item in actions]}


def ollama_advise(
    payload: dict[str, Any],
    policy: dict[str, Any],
    *,
    transport: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a bounded, model-derived advisory without exposing raw model output."""
    raw = canonical_json(payload)
    allowed_fields = {"task", "policy_path"}
    if set(payload) - allowed_fields or not isinstance(payload.get("task"), str) or not payload["task"].strip():
        return result("ollama_advisory", "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_ollama_advisory_input"}])
    task = payload["task"].strip()
    if len(task.encode("utf-8")) > 4096:
        return result("ollama_advisory", "stdin", raw, {}, status="invalid_input", errors=[{"code": "ollama_task_size_exceeded"}])
    config = policy.get("ollama", {})
    model, endpoint = config.get("model"), config.get("endpoint")
    if not isinstance(model, str) or not model or not isinstance(endpoint, str) or not endpoint:
        return result("ollama_advisory", "stdin", raw, {}, status="policy_blocked", errors=[{"code": "ollama_runtime_not_configured"}])
    request_payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": ADVICE_SCHEMA,
        "options": {"temperature": 0},
        "prompt": (
            "Provide a short read-only coding advisory for the supplied task. "
            "Do not claim execution, do not request secrets, and return only JSON matching the schema.\n"
            + canonical_json({"task": task})
        ),
    }
    timeout = int(config.get("timeout_seconds", policy.get("limits", {}).get("timeout_seconds", 60)))
    call = transport or (lambda guarded_endpoint, body: _transport(guarded_endpoint, body, timeout=timeout))
    try:
        policy_result, candidate = guarded_inference_call(endpoint, request_payload, call)
    except (KeyError, TypeError, ValueError, OSError, TimeoutError, urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        policy_result, candidate = None, None
    if policy_result is not None and policy_result["status"] != "success":
        return result(
            "ollama_advisory", "stdin", raw,
            {"terminal_status": "blocked", "advisory_status": "not_run", "raw_response_retained": False,
             "endpoint_policy": "loopback_only", "physical_inference_locality": "not_provable"},
            status="policy_blocked", errors=policy_result["errors"],
        )
    advice = _safe_advice(candidate)
    if advice is None:
        return result(
            "ollama_advisory", "stdin", raw,
            {"terminal_status": "failed", "advisory_status": "unavailable", "raw_response_retained": False,
             "endpoint_policy": "loopback_only", "physical_inference_locality": "not_provable"},
            status="partial", errors=[{"code": "ollama_advisory_unavailable"}],
        )
    locality = policy_result["data"]
    return result(
        "ollama_advisory", "stdin", raw,
        {"terminal_status": "pass", "advisory_status": "accepted", "model": model, "advice": advice,
         "raw_response_retained": False, "endpoint_policy": "loopback_only",
         "local_runtime_verified": locality.get("local_runtime_verified", False),
         "physical_inference_locality": locality.get("physical_inference_locality", "not_provable")},
    )
