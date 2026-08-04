from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from .contracts import canonical_json, result
from .policy import guarded_inference_call, load_policy
from .stage_b_gate import build_inference_payload, evaluate_candidate_response


CANDIDATE_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["groups", "excluded"],
    "properties": {
        "groups": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "group_id", "pattern", "classification", "source_span",
                    "confidence", "origin", "needs_review",
                ],
                "properties": {
                    "group_id": {"type": "string", "pattern": "^SG-[A-Z0-9_-]+$"},
                    "pattern": {"type": "string"},
                    "classification": {"type": "string"},
                    "source_span": {
                        "type": "array", "items": {"type": "string"},
                        "minItems": 1, "uniqueItems": True,
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "origin": {"const": "model-derived"},
                    "needs_review": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        },
        "excluded": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["event_id", "reason"],
                "properties": {
                    "event_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

V2_CANDIDATE_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["contract_version", "groups", "ungrouped_candidate_ids"],
    "properties": {
        "contract_version": {"const": 2},
        "groups": CANDIDATE_RESPONSE_SCHEMA["properties"]["groups"],
        "ungrouped_candidate_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
    },
    "additionalProperties": False,
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _valid_parsed_events(events: list[Any]) -> bool:
    required = {
        "event_id", "level", "component", "message", "raw_hash",
        "raw_line_start", "raw_line_end", "parse_status",
    }
    parse_states = {"parsed", "part_of_event", "unknown_event", "unsupported_format", "parse_failed"}
    if not events:
        return False
    for event in events:
        if not isinstance(event, dict) or not required <= set(event):
            return False
        start, end = event.get("raw_line_start"), event.get("raw_line_end")
        if (
            not isinstance(event.get("event_id"), str)
            or not re.fullmatch(r"EV-\d{6}", event["event_id"])
            or not all(isinstance(event.get(field), str) for field in ("level", "component", "message"))
            or not isinstance(event.get("raw_hash"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", event["raw_hash"])
            or not isinstance(start, int) or isinstance(start, bool) or start < 1
            or not isinstance(end, int) or isinstance(end, bool) or end < start
            or event.get("parse_status") not in parse_states
            or event.get("origin", "observed") != "observed"
        ):
            return False
    return True


def ollama_transport(endpoint: str, request_payload: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=canonical_json(request_payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        body = response.read(1_000_001)
    if len(body) > 1_000_000:
        raise ValueError("model_response_too_large")
    envelope = json.loads(body)
    candidate = json.loads(envelope["response"])
    if not isinstance(candidate, dict):
        raise ValueError("invalid_model_response")
    return candidate


def log_cluster(
    payload: dict[str, Any],
    policy: dict[str, Any] | None = None,
    *,
    transport: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    raw = canonical_json(payload)
    active_policy = policy if policy is not None else load_policy(payload.get("policy_path"))
    semantic = active_policy.get("semantic", {})
    events = payload.get("events")
    model = semantic.get("model")
    endpoint = semantic.get("endpoint")
    if not isinstance(events, list):
        return result(
            "semantic_log_cluster", "stdin", raw, {}, status="invalid_input",
            errors=[{"code": "parsed_log_events_required"}],
        )
    if not isinstance(model, str) or not model or not isinstance(endpoint, str) or not endpoint:
        return result(
            "semantic_log_cluster", "stdin", raw, {}, status="policy_blocked",
            errors=[{"code": "semantic_runtime_not_configured"}],
        )
    if not _valid_parsed_events(events):
        return result(
            "semantic_log_cluster", "stdin", raw, {}, status="invalid_input",
            errors=[{"code": "parsed_log_events_required"}],
        )
    v2 = payload.get("contract_version") == 2
    try:
        inference_payload = build_inference_payload(events)
    except (TypeError, ValueError):
        return result(
            "semantic_log_cluster", "stdin", raw,
            {"fallback_used": False, "semantic_groups": []},
            status="policy_blocked", errors=[{"code": "unsafe_or_invalid_log_events"}],
        )
    if v2:
        candidate_events = [{key: value for key, value in event.items() if key in {"event_id", "level", "component", "message", "exception_type", "source_file", "source_line"}} for event in inference_payload["events"]]
        model_input = {"contract_version": 2, "candidate_events": candidate_events}
        prompt = ("Group only the supplied candidate events by concrete failure pattern. "
                  "Every candidate ID must occur exactly once in groups or ungrouped_candidate_ids. "
                  "Never invent IDs. Keep distinct failure types separate. Return only JSON matching the schema.\n" + canonical_json(model_input))
    else:
        prompt = (
            "Group repeated failure events by the same concrete failure pattern. "
            "Account for every event exactly once using groups or excluded. "
            "Never invent event IDs. Keep distinct failure types separate. "
            "Return only JSON matching the supplied schema.\n"
            + canonical_json(inference_payload)
        )
    request_payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": V2_CANDIDATE_RESPONSE_SCHEMA if v2 else CANDIDATE_RESPONSE_SCHEMA,
        "options": {"temperature": 0},
    }
    timeout = int(active_policy.get("limits", {}).get("timeout_seconds", 60))
    call = transport or (lambda guarded_endpoint, body: ollama_transport(guarded_endpoint, body, timeout=timeout))
    try:
        policy_result, candidate = guarded_inference_call(endpoint, request_payload, call)
    except (KeyError, TypeError, ValueError, OSError, TimeoutError, urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        candidate = None
        policy_result = None
    if policy_result is not None and policy_result["status"] != "success":
        return result(
            "semantic_log_cluster", "stdin", raw,
            {"fallback_used": False, "semantic_groups": []},
            status="policy_blocked", errors=policy_result["errors"],
        )
    if v2:
        if candidate is None:
            return result("semantic_log_cluster", "stdin", raw, {"fallback_used": True, "fallback_reason": ["model_unavailable"], "semantic_groups": []}, status="partial", warnings=[{"code": "semantic_fallback_used"}])
        # Retain only the contract fields; provider envelopes and raw text never escape.
        safe_candidate = ({key: candidate.get(key) for key in ("contract_version", "groups", "ungrouped_candidate_ids")} if isinstance(candidate, dict) else candidate)
        return result("semantic_log_cluster", "stdin", raw, {"fallback_used": False, "fallback_reason": [], "candidate_response": safe_candidate, "semantic_groups": [], "model": model, "endpoint_policy": "loopback_only"})
    evaluation = evaluate_candidate_response(
        inference_payload["events"],
        candidate,
        failure="model_unavailable" if candidate is None else None,
    )
    status = evaluation.pop("status")
    data = {**evaluation, "model": model, "endpoint_policy": "loopback_only"}
    warnings = [{"code": "semantic_fallback_used"}] if data["fallback_used"] else []
    return result("semantic_log_cluster", "stdin", raw, data, status=status, warnings=warnings)
