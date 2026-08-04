from __future__ import annotations

from collections import Counter
from typing import Any, Callable

from .contracts import canonical_json, result
from .stage_b_accounting import candidate_events, final_accounting, initial_dispositions, validate_v2_candidate
from .stage_b_cluster import log_cluster
from .tools import parse_log


def _repeated_failure_signatures(events: list[dict[str, Any]]) -> bool:
    signatures = [
        (event.get("component"), event.get("level"), event.get("message"))
        for event in events
        if event.get("level") == "error"
    ]
    return any(count > 1 for count in Counter(signatures).values())


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
    events = stage_a["data"]["events"]
    preliminary = initial_dispositions(events)
    candidates = candidate_events(events, preliminary)
    semantic_value = payload.get("semantic")
    if semantic_value is not None and not isinstance(semantic_value, bool):
        return result("log_process", "stdin", raw, {}, status="invalid_input", errors=[{"code": "semantic_must_be_boolean"}])
    semantic = policy.get("semantic", {})
    automatic = policy.get("automatic", {})
    enabled = automatic.get("semantic_log_clustering") is True and semantic.get("enabled") is True
    automatic_routing = semantic.get("automatic_routing") is True
    threshold = int(semantic.get("routing_event_threshold", 8))
    routed = semantic_value is True or automatic_routing and (
        len(candidates) >= threshold or _repeated_failure_signatures(candidates)
    )
    timed_out = int(policy.get("limits", {}).get("timeout_seconds", 60)) <= 0
    attempted = enabled and semantic_value is not False and routed and bool(candidates) and not timed_out
    groups: list[dict[str, Any]] = []
    ungrouped: list[str] = []
    fallback = False
    accepted = False
    reasons: list[str] = []
    errors: list[dict[str, Any]] = []
    status = stage_a["status"]
    if semantic.get("code_artifact", "disabled") != "disabled":
        attempted = False
        fallback = True
        reasons = ["semantic_code_artifact_prohibited"]
        errors = [{"code": reasons[0]}]
        status = "policy_blocked"
    elif attempted:
        cluster = log_cluster({"events": candidates, "contract_version": 2}, policy, transport=transport)
        if cluster["status"] == "policy_blocked":
            fallback = True
            reasons = [error["code"] for error in cluster["errors"]]
            errors = cluster["errors"]
            status = "policy_blocked"
        elif cluster["status"] != "success":
            fallback = True
            reasons = cluster.get("data", {}).get("fallback_reason", ["model_unavailable"])
            status = "partial"
        else:
            candidate = cluster["data"].get("candidate_response")
            validated = validate_v2_candidate(
                candidates,
                candidate,
                catchall_share=float(semantic.get("catchall_group_share", 0.8)),
            )
            if validated["accepted"]:
                groups = validated["groups"]
                ungrouped = validated["ungrouped"]
                accepted = True
            else:
                fallback = True
                reasons = validated["errors"]
                status = "partial"
    elif semantic_value is True and not candidates:
        fallback = True
        reasons = ["no_model_candidates"]
        status = "partial"
    elif enabled and semantic_value is not False and routed and timed_out:
        fallback = True
        reasons = ["timeout_before_execution"]
        status = "partial"

    final, accounting = final_accounting(events, preliminary, groups, ungrouped, fallback=fallback)
    warnings = list(stage_a["warnings"])
    if fallback:
        warnings.append({"code": "semantic_fallback_used"})
    if accounting["unclassified_observed_total"] > int(semantic.get("unclassified_observed_threshold", 0)):
        warnings.append({"code": "unclassified_observed_excessive"})
        status = "partial"
    data = {
        "semantic_log_grouping_contract": 2,
        "stage_a": stage_a["data"],
        "observed_events": [{**event, "origin": "observed"} for event in events],
        "initial_dispositions": preliminary,
        "model_candidate_events": candidates,
        "semantic_groups": groups,
        "final_dispositions": final,
        "accounting": accounting,
        "semantic_attempted": attempted,
        "semantic_accepted": accepted,
        "fallback_used": fallback,
        "fallback_reason": reasons,
    }
    return result("log_process", str(payload.get("source", "stdin")), raw, data, status=status, warnings=warnings, errors=errors)
