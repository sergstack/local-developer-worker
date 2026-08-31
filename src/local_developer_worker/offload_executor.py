from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable

from .codex_runner import codex_run
from .contracts import canonical_json, result, valid_tool_result
from .ollama_advisor import ollama_advise
from .policy import allowed, root_allowed


OFFLOAD_MODES = frozenset({"local_first", "candidate_review", "frontier_floor", "blocked"})
RISK_FLOORS = frozenset({"efficient", "balanced", "frontier"})
DETERMINISTIC_POLICIES = frozenset({"use_if_available", "skip"})
FRONTIER_POLICIES = frozenset({"allowed", "forbidden"})
POLICY_REVISION = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
DETERMINISTIC_TOOLS = frozenset({
    "structured_log_parser", "test_result_parser", "git_facts_collector",
    "file_inventory", "context_packer", "context_refresher", "context_compactor",
    "change_summarizer",
})

Executor = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def _public_data(payload: dict[str, Any], **updates: Any) -> dict[str, Any]:
    return {
        "contract_version": "1.0.0",
        "task_class": payload["task_class"],
        "risk_floor": payload["risk_floor"],
        "offload_mode": payload["offload_mode"],
        "verification_kind": payload["verification_kind"],
        "fallback_policy": payload["fallback_policy"],
        "policy_revision": payload["policy_revision"],
        "selected_route": None,
        "terminal_status": "blocked",
        "authority_status": "caller_owned",
        "candidate_provenance": None,
        "candidate": None,
        "local_capability": {"runtime": "not_checked", "model": "not_checked"},
        "fallback_used": False,
        "fallback_reason": None,
        "deterministic_result_ref": None,
        "route_result": None,
        "local_model_invoked": False,
        "local_latency_ms": None,
        "verification_status": "not_run",
        "context_metrics": {"before_bytes": None, "after_bytes": None, "reduced_bytes": None},
        **updates,
    }


def _validate(payload: dict[str, Any]) -> str | None:
    allowed_fields = {
        "task", "task_class", "risk_floor", "offload_mode", "verification_kind",
        "fallback_policy", "policy_revision", "policy_path", "repository_root",
        "verification", "deterministic_result", "context_bytes_before", "context_bytes_after",
    }
    if set(payload) - allowed_fields:
        return "unknown_offload_input_fields"
    if not isinstance(payload.get("task"), str) or not payload["task"].strip() or len(payload["task"].encode()) > 4096:
        return "invalid_offload_task"
    if not isinstance(payload.get("task_class"), str) or OPAQUE_IDENTIFIER.fullmatch(payload["task_class"]) is None:
        return "invalid_offload_task_class"
    if payload.get("risk_floor") not in RISK_FLOORS or payload.get("offload_mode") not in OFFLOAD_MODES:
        return "invalid_offload_policy_envelope"
    if not isinstance(payload.get("verification_kind"), str) or not payload["verification_kind"].strip():
        return "invalid_offload_verification_kind"
    if not isinstance(payload.get("policy_revision"), str) or not POLICY_REVISION.fullmatch(payload["policy_revision"]):
        return "invalid_offload_policy_revision"
    fallback = payload.get("fallback_policy")
    if (
        not isinstance(fallback, dict)
        or set(fallback) != {"deterministic", "frontier"}
        or fallback.get("deterministic") not in DETERMINISTIC_POLICIES
        or fallback.get("frontier") not in FRONTIER_POLICIES
    ):
        return "invalid_offload_fallback_policy"
    before, after = payload.get("context_bytes_before"), payload.get("context_bytes_after")
    if (before is None) != (after is None) or (before is not None and (
        not isinstance(before, int) or isinstance(before, bool) or before < 0
        or not isinstance(after, int) or isinstance(after, bool) or after < 0 or after > before
    )):
        return "invalid_offload_context_measurement"
    deterministic = payload.get("deterministic_result")
    if deterministic is not None and (
        not isinstance(deterministic, dict)
        or not valid_tool_result(deterministic)
        or deterministic.get("status") != "success"
        or deterministic.get("tool") not in DETERMINISTIC_TOOLS
        or not isinstance(deterministic.get("run_id"), str)
        or not deterministic["run_id"]
    ):
        return "invalid_deterministic_result"
    return None


def _context_metrics(payload: dict[str, Any]) -> dict[str, int | None]:
    before, after = payload.get("context_bytes_before"), payload.get("context_bytes_after")
    return {"before_bytes": before, "after_bytes": after, "reduced_bytes": before - after if isinstance(before, int) and isinstance(after, int) else None}


def _local_capability(local: dict[str, Any]) -> dict[str, str]:
    data = local.get("data", {}) if isinstance(local.get("data"), dict) else {}
    runtime = data.get("local_runtime_state")
    model = data.get("local_model_state")
    if runtime not in {"available", "unavailable", "policy_blocked", "incompatible", "not_configured", "unknown"}:
        runtime = "available" if local.get("status") == "success" else "unknown"
    if model not in {"available", "unavailable", "not_configured", "unknown"}:
        model = "available" if local.get("status") == "success" else "unknown"
    return {"runtime": runtime, "model": model}


def _frontier(
    payload: dict[str, Any],
    policy: dict[str, Any],
    raw: str,
    data: dict[str, Any],
    frontier_executor: Executor,
    reason: str,
) -> dict[str, Any]:
    if payload["fallback_policy"]["frontier"] != "allowed":
        return result(
            "offload_executor", "stdin", raw,
            {**data, "fallback_reason": reason},
            status="policy_blocked", errors=[{"code": "frontier_fallback_forbidden"}],
        )
    root = payload.get("repository_root")
    if not isinstance(root, str) or not root or not root_allowed(policy, root, Path.cwd()):
        return result(
            "offload_executor", "stdin", raw,
            {**data, "selected_route": "frontier", "fallback_used": True, "fallback_reason": reason},
            status="policy_blocked", errors=[{"code": "frontier_repository_root_not_allowed"}],
        )
    verification = payload.get("verification", {"kind": "execution"})
    if not isinstance(verification, dict) or verification.get("kind") != payload["verification_kind"]:
        return result(
            "offload_executor", "stdin", raw,
            {**data, "selected_route": "frontier", "fallback_used": True, "fallback_reason": reason},
            status="invalid_input", errors=[{"code": "frontier_verification_mismatch"}],
        )
    frontier = frontier_executor(
        {
            "task": payload["task"],
            "repository_root": root,
            "policy_path": payload.get("policy_path"),
            "profile": payload["risk_floor"],
            "verification": verification,
        },
        policy,
    )
    frontier_data = frontier.get("data", {}) if isinstance(frontier.get("data"), dict) else {}
    passed = frontier.get("status") == "success" and frontier_data.get("terminal_status") == "pass"
    public = {
        **data,
        "selected_route": "frontier",
        "terminal_status": "pass" if passed else frontier_data.get("terminal_status", "blocked"),
        "fallback_used": reason != "frontier_floor",
        "fallback_reason": reason,
        "route_result": {
            "tool": frontier.get("tool"), "run_id": frontier.get("run_id"),
            "status": frontier.get("status"), "terminal_status": frontier_data.get("terminal_status"),
            "verification_status": frontier_data.get("verification_status"),
            "input_tokens": frontier_data.get("input_tokens"), "cached_input_tokens": frontier_data.get("cached_input_tokens"),
            "output_tokens": frontier_data.get("output_tokens"), "reasoning_output_tokens": frontier_data.get("reasoning_output_tokens"),
            "fallback_count": frontier_data.get("fallback_count", 0), "escalation_count": frontier_data.get("escalation_count", 0),
        },
        "verification_status": frontier_data.get("verification_status", "not_run"),
    }
    if passed:
        return result("offload_executor", "stdin", raw, public)
    status = frontier.get("status") if frontier.get("status") in {"partial", "policy_blocked", "timeout"} else "partial"
    return result("offload_executor", "stdin", raw, public, status=status, errors=[{"code": "frontier_route_not_successful"}])


def offload_execute(
    payload: dict[str, Any],
    policy: dict[str, Any],
    *,
    local_executor: Executor = ollama_advise,
    frontier_executor: Executor = codex_run,
) -> dict[str, Any]:
    """Execute only the route authorized by a caller-owned AI-OS policy envelope."""
    raw = canonical_json(payload)
    error = _validate(payload)
    if error:
        return result("offload_executor", "stdin", raw, {}, status="invalid_input", errors=[{"code": error}])
    data = _public_data(payload, context_metrics=_context_metrics(payload))
    mode = payload["offload_mode"]
    if mode == "blocked":
        return result("offload_executor", "stdin", raw, data, status="policy_blocked", errors=[{"code": "offload_policy_blocked"}])
    if mode == "frontier_floor":
        return _frontier(payload, policy, raw, data, frontier_executor, "frontier_floor")

    local_enabled = policy.get("ollama", {}).get("enabled") is True and allowed(policy, "ollama_readonly_advisory")
    if local_enabled:
        local_started = time.perf_counter()
        local = local_executor({"task": payload["task"], "policy_path": payload.get("policy_path")}, policy)
        local_latency_ms = round((time.perf_counter() - local_started) * 1000)
    else:
        local = result(
            "ollama_advisory", "stdin", raw,
            {"local_runtime_state": "policy_blocked", "local_model_state": "unknown"},
            status="policy_blocked", errors=[{"code": "ollama_advisory_disabled"}],
        )
        local_latency_ms = None
    capability = _local_capability(local)
    local_data = local.get("data", {}) if isinstance(local.get("data"), dict) else {}
    if local.get("status") == "success" and local_data.get("advisory_status") == "accepted":
        return result(
            "offload_executor", "stdin", raw,
            {
                **data,
                "selected_route": "local",
                "terminal_status": "candidate_ready",
                "authority_status": "candidate_only",
                "candidate_provenance": {"source": "local_model", "tool": local.get("tool"), "run_id": local.get("run_id")},
                "candidate": local_data.get("advice"),
                "local_capability": capability,
                "local_model_invoked": True,
                "local_latency_ms": local_latency_ms,
                "verification_status": "schema_valid",
                "route_result": {"tool": local.get("tool"), "run_id": local.get("run_id"), "status": local.get("status")},
            },
        )

    reason = "local_route_unavailable"
    deterministic = payload.get("deterministic_result")
    if payload["fallback_policy"]["deterministic"] == "use_if_available" and deterministic is not None:
        return result(
            "offload_executor", "stdin", raw,
            {
                **data,
                "selected_route": "deterministic",
                "terminal_status": "pass",
                "local_capability": capability,
                "local_model_invoked": local_enabled,
                "local_latency_ms": local_latency_ms,
                "verification_status": "observed_success",
                "fallback_used": True,
                "fallback_reason": reason,
                "deterministic_result_ref": {"tool": deterministic.get("tool"), "run_id": deterministic["run_id"]},
                "route_result": {"tool": deterministic.get("tool"), "run_id": deterministic["run_id"], "status": "success"},
            },
        )
    return _frontier(
        payload, policy, raw,
        {**data, "local_capability": capability, "local_model_invoked": local_enabled, "local_latency_ms": local_latency_ms},
        frontier_executor, reason,
    )
