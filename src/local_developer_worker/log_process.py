from __future__ import annotations

from collections import Counter
from typing import Any, Callable

from .contracts import canonical_json, result
from .stage_b_cluster import log_cluster
from .tools import parse_log


def _valid_observed_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event.get("parse_status") == "parsed"]


def _repeated_failure_signatures(events: list[dict[str, Any]]) -> bool:
    signatures = [
        (event.get("component"), event.get("level"), event.get("message"))
        for event in events
        if event.get("level") == "error"
    ]
    return any(count > 1 for count in Counter(signatures).values())


def _source_accounting(events: list[dict[str, Any]], groups: list[dict[str, Any]]) -> list[dict[str, str]]:
    group_by_event = {
        event_id: group["group_id"]
        for group in groups
        for event_id in group["source_span"]
    }
    return [
        {
            "event_id": event["event_id"],
            "disposition": "semantic_group" if event["event_id"] in group_by_event else "stage_a_observed",
            **({"group_id": group_by_event[event["event_id"]]} if event["event_id"] in group_by_event else {}),
        }
        for event in events
    ]


def log_process(
    payload: dict[str, Any],
    policy: dict[str, Any],
    *,
    transport: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    raw = canonical_json(payload)
    stage_a = parse_log(payload)
    if stage_a["status"] == "invalid_input":
        return result("log_process", "stdin", raw, {}, status="invalid_input", errors=stage_a["errors"])
    all_events = stage_a["data"]["events"]
    valid_events = _valid_observed_events(all_events)
    semantic_value = payload.get("semantic")
    if semantic_value is not None and not isinstance(semantic_value, bool):
        return result("log_process", "stdin", raw, {}, status="invalid_input", errors=[{"code": "semantic_must_be_boolean"}])
    semantic = policy.get("semantic", {})
    automatic = policy.get("automatic", {})
    if semantic.get("code_artifact", "disabled") != "disabled":
        return result(
            "log_process", str(payload.get("source", "stdin")), raw,
            {"stage_a": stage_a["data"], "observed_events": [{**event, "origin": "observed"} for event in all_events], "semantic_groups": [], "source_accounting": _source_accounting(all_events, []), "semantic_attempted": False, "semantic_accepted": False, "fallback_used": True, "fallback_reason": ["semantic_code_artifact_prohibited"]},
            status="policy_blocked", errors=[{"code": "semantic_code_artifact_prohibited"}],
        )
    threshold = int(semantic.get("routing_event_threshold", 8))
    enabled = automatic.get("semantic_log_clustering") is True and semantic.get("enabled") is True
    requested = semantic_value is True
    routed = requested or len(valid_events) >= threshold or _repeated_failure_signatures(valid_events)
    timed_out = int(policy.get("limits", {}).get("timeout_seconds", 60)) <= 0
    attempted = enabled and semantic_value is not False and routed and bool(valid_events) and not timed_out
    groups: list[dict[str, Any]] = []
    fallback_used = False
    accepted = False
    warnings = list(stage_a["warnings"])
    errors: list[dict[str, Any]] = []
    status = stage_a["status"]
    fallback_reason: list[str] = []
    if attempted:
        clustered = log_cluster({"events": valid_events}, policy, transport=transport)
        groups = clustered.get("data", {}).get("semantic_groups", [])
        fallback_used = bool(clustered.get("data", {}).get("fallback_used"))
        accepted = clustered["status"] == "success" and not fallback_used
        fallback_reason = clustered.get("data", {}).get("fallback_reason", [])
        if clustered["status"] == "policy_blocked":
            fallback_used = True
            fallback_reason = [error["code"] for error in clustered["errors"]]
            errors = clustered["errors"]
            status = "policy_blocked"
        if fallback_used:
            warnings.append({"code": "semantic_fallback_used"})
            if status != "policy_blocked":
                status = "partial"
    elif semantic_value is True and not valid_events:
        fallback_used = True
        fallback_reason = ["no_valid_observed_events"]
        status = "partial"
        warnings.append({"code": "semantic_fallback_used"})
    elif enabled and semantic_value is not False and routed and timed_out:
        fallback_used = True
        fallback_reason = ["timeout_before_execution"]
        status = "partial"
        warnings.append({"code": "semantic_fallback_used"})
    data = {
        "stage_a": stage_a["data"],
        "observed_events": [{**event, "origin": "observed"} for event in all_events],
        "semantic_groups": groups,
        "source_accounting": _source_accounting(all_events, groups),
        "semantic_attempted": attempted,
        "semantic_accepted": accepted,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
    }
    return result("log_process", str(payload.get("source", "stdin")), raw, data, status=status, warnings=warnings, errors=errors)
