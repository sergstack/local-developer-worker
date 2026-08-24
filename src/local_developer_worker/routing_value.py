"""Render one privacy-safe, observable routing value summary.

The renderer consumes an existing ``ldw codex run`` ToolResult.  It never
launches a model, alters policy, or manufactures a baseline for savings claims.
"""

from __future__ import annotations

from typing import Any

from .contracts import canonical_json, result, valid_tool_result
from .session_log import iter_records


RUN_FIELDS = {
    "execution_id", "profile", "model_alias", "effort", "routing_signal",
    "routing_confidence", "deterministic_risk_floor", "terminal_status",
    "verification_status", "fallback_count", "escalation_count",
    "execution_attempted", "model_execution_completed", "calibration_eligible",
    "input_tokens", "cached_input_tokens", "non_cached_input_tokens",
    "output_tokens", "reasoning_output_tokens", "provider_total_tokens",
    "reasoning_in_output_status", "policy_revision",
}
CONTEXT_FIELDS = {"candidate_bytes", "selected_bytes", "critical_recall", "sensitive_block_count"}


def _not_measured(reason: str) -> dict[str, str]:
    return {"status": "not_measured", "reason": reason}


def _latency(data: dict[str, Any], journal_root: str | None) -> tuple[dict[str, Any], str | None]:
    execution_id = data["execution_id"]
    records, invalid = iter_records(journal_root)
    matches = [
        item for item in records
        if item.get("record_type") == "codex_routing_event_v2" and item.get("execution_id") == execution_id
    ]
    if invalid:
        return _not_measured("journal_contains_invalid_records"), "journal_contains_invalid_records"
    if len(matches) != 1:
        return _not_measured("matching_routing_observation_not_found" if not matches else "matching_routing_observation_ambiguous"), None
    event = matches[0]
    if event.get("final_profile") != data["profile"] or event.get("final_effort") != data["effort"]:
        return _not_measured("matching_routing_observation_conflicts"), "matching_routing_observation_conflicts"
    latency_ms = event.get("latency_ms")
    if not isinstance(latency_ms, int) or isinstance(latency_ms, bool) or latency_ms < 0:
        return _not_measured("matching_routing_latency_not_observed"), None
    return {"status": "observed", "latency_ms": latency_ms}, None


def _context(value: Any) -> tuple[dict[str, Any], str | None]:
    if value is None:
        return _not_measured("context_observation_not_supplied"), None
    if not isinstance(value, dict) or set(value) != CONTEXT_FIELDS:
        return _not_measured("invalid_context_observation"), "invalid_context_observation"
    candidate, selected = value["candidate_bytes"], value["selected_bytes"]
    recall, blocks = value["critical_recall"], value["sensitive_block_count"]
    if (
        not all(isinstance(item, int) and not isinstance(item, bool) and item >= 0 for item in (candidate, selected, blocks))
        or selected > candidate
        or not isinstance(recall, (int, float))
        or isinstance(recall, bool)
        or not 0 <= recall <= 1
    ):
        return _not_measured("invalid_context_observation"), "invalid_context_observation"
    reduction = None if candidate == 0 else round((candidate - selected) / candidate, 4)
    return {
        "status": "observed", "candidate_bytes": candidate, "selected_bytes": selected,
        "context_reduction": reduction, "critical_recall": recall, "sensitive_block_count": blocks,
    }, None


def routing_value(payload: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return observed route facts, never a counterfactual savings claim."""
    raw = canonical_json(payload)
    allowed = {"codex_result", "journal_root", "context_observation", "policy_path"}
    source = payload.get("codex_result")
    if set(payload) - allowed or not isinstance(source, dict) or not valid_tool_result(source) or source.get("tool") != "codex_run":
        return result("routing_value", "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_routing_value_input"}])
    data = source.get("data")
    if not isinstance(data, dict) or not RUN_FIELDS <= set(data):
        return result("routing_value", "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_routing_value_input"}])
    journal_root = payload.get("journal_root")
    if journal_root is not None and (not isinstance(journal_root, str) or not journal_root):
        return result("routing_value", "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_routing_value_input"}])
    latency, latency_warning = _latency(data, journal_root)
    context, context_warning = _context(payload.get("context_observation"))
    warnings = [{"code": item} for item in (latency_warning, context_warning) if item]
    output = {
        "contract_version": "1.0.0",
        "execution_id": data["execution_id"],
        "observed": {
            "route": {
                "profile": data["profile"], "model_alias": data["model_alias"], "effort": data["effort"],
                "routing_signal": data["routing_signal"], "routing_confidence": data["routing_confidence"],
                "deterministic_risk_floor": data["deterministic_risk_floor"], "policy_revision": data["policy_revision"],
            },
            "execution": {
                "terminal_status": data["terminal_status"], "verification_status": data["verification_status"],
                "execution_attempted": data["execution_attempted"], "model_execution_completed": data["model_execution_completed"],
                "fallback_count": data["fallback_count"], "escalation_count": data["escalation_count"],
            },
            "latency": latency,
            "tokens": {
                "input_tokens": data["input_tokens"], "cached_input_tokens": data["cached_input_tokens"],
                "non_cached_input_tokens": data["non_cached_input_tokens"], "output_tokens": data["output_tokens"],
                "reasoning_output_tokens": data["reasoning_output_tokens"], "provider_total_tokens": data["provider_total_tokens"],
                "reasoning_in_output_status": data["reasoning_in_output_status"],
            },
        },
        "comparison": {"status": "not_available", "reason": "matched_control_not_supplied"},
        "context": context,
        "quality": _not_measured("child_findings_not_exposed_by_tool_result"),
        "claim_boundary": "No savings, speedup, context-cleanliness, or semantic-quality claim is made without its required observed evidence.",
    }
    return result("routing_value", "stdin", raw, output, status="partial" if warnings else "success", warnings=warnings)
