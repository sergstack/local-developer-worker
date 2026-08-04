from __future__ import annotations

from collections import Counter
from typing import Any


EXCLUSION_REASONS = {
    "empty_structural_line",
    "known_non_failure_metadata",
    "duplicate_stage_a_fragment",
    "already_accounted_continuation",
    "unsupported_but_nonsemantic_record",
}


def initial_dispositions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classify every Stage A event without making a semantic judgement."""
    rows: list[dict[str, Any]] = []
    parent: str | None = None
    seen: set[tuple[str, str, str]] = set()
    for event in events:
        event_id = event["event_id"]
        message = event.get("message", "")
        state = event.get("parse_status")
        if event.get("policy_blocked") is True:
            rows.append({"event_id": event_id, "disposition": "policy_blocked", "reason_code": "policy_blocked_content", "rule_id": "PB4-03-POLICY"})
        elif parent and (state == "part_of_event" or (state == "unknown_event" and isinstance(message, str) and message[:1].isspace())):
            rows.append({"event_id": event_id, "disposition": "structural_continuation", "parent_event_id": parent, "reason_code": "continuation_of_parent_event", "rule_id": "PB4-03-CONTINUATION", "evidence": {"parent_event_id": parent}})
        elif not message.strip():
            rows.append({"event_id": event_id, "disposition": "deterministically_excluded", "reason_code": "empty_structural_line", "rule_id": "PB4-03-EMPTY", "evidence": {"message_empty": True}})
        elif state == "unsupported_format" and event.get("level") in {"info", "unknown"}:
            rows.append({"event_id": event_id, "disposition": "deterministically_excluded", "reason_code": "unsupported_but_nonsemantic_record", "rule_id": "PB4-03-UNSUPPORTED", "evidence": {"parse_status": state}})
        elif state == "parsed" and event.get("level") == "info":
            rows.append({"event_id": event_id, "disposition": "deterministically_excluded", "reason_code": "known_non_failure_metadata", "rule_id": "PB4-03-INFO-METADATA", "evidence": {"level": "info", "parse_status": "parsed"}})
        else:
            fingerprint = (str(event.get("level")), str(event.get("component")), str(message))
            if fingerprint in seen and state == "part_of_event":
                rows.append({"event_id": event_id, "disposition": "deterministically_excluded", "reason_code": "duplicate_stage_a_fragment", "rule_id": "PB4-03-DUPLICATE", "evidence": {"fingerprint": "duplicate"}})
            elif state in {"parse_failed"}:
                rows.append({"event_id": event_id, "disposition": "unclassified_observed", "reason_code": "stage_a_parse_failed", "rule_id": "PB4-03-UNCLASSIFIED"})
            else:
                # Unknown events deliberately stay visible; no state is excluded by default.
                rows.append({"event_id": event_id, "disposition": "model_candidate", "reason_code": "independently_observed", "rule_id": "PB4-03-CANDIDATE"})
                parent = event_id
            seen.add(fingerprint)
    return rows


def candidate_events(events: list[dict[str, Any]], dispositions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = {row["event_id"] for row in dispositions if row["disposition"] == "model_candidate"}
    return [event for event in events if event["event_id"] in ids]


def validate_v2_candidate(events: list[dict[str, Any]], response: Any, *, catchall_share: float = 0.8) -> dict[str, Any]:
    ids = {event["event_id"] for event in events}
    events_by_id = {event["event_id"]: event for event in events}
    if not isinstance(response, dict) or response.get("contract_version") != 2:
        return {"accepted": False, "errors": ["invalid_v2_candidate_contract"], "groups": [], "ungrouped": []}
    if set(response) != {"contract_version", "groups", "ungrouped_candidate_ids"}:
        return {"accepted": False, "errors": ["invalid_v2_candidate_contract"], "groups": [], "ungrouped": []}
    groups, ungrouped = response.get("groups"), response.get("ungrouped_candidate_ids")
    if not isinstance(groups, list) or not isinstance(ungrouped, list) or not all(isinstance(i, str) for i in ungrouped):
        return {"accepted": False, "errors": ["invalid_v2_candidate_contract"], "groups": [], "ungrouped": []}
    errors: list[str] = []
    claimed: list[str] = []
    normalized: list[dict[str, Any]] = []
    generic = {"failure", "error", "errors", "unknown", "generic"}
    for group in groups:
        required = {"group_id", "pattern", "classification", "source_span", "confidence", "origin", "needs_review"}
        if not isinstance(group, dict) or set(group) != required or group.get("origin") != "model-derived":
            errors.append("invalid_group_contract"); continue
        span = group.get("source_span")
        if not isinstance(span, list) or not span or not all(isinstance(i, str) for i in span):
            errors.append("invalid_source_span"); continue
        if not isinstance(group.get("pattern"), str) or not group["pattern"] or not isinstance(group.get("classification"), str) or not group["classification"]:
            errors.append("invalid_group_contract")
        if isinstance(group.get("confidence"), bool) or not isinstance(group.get("confidence"), (int, float)) or not 0 <= group["confidence"] <= 1 or not isinstance(group.get("needs_review"), bool):
            errors.append("invalid_group_contract")
        if any(i not in ids for i in span): errors.append("invented_candidate_id")
        claimed.extend(span)
        share = len(span) / len(ids) if ids else 0
        if share > catchall_share and (group["pattern"].strip().lower() in generic or group["classification"].strip().lower() in generic):
            errors.append("catch_all_group")
        components = {str(events_by_id[event_id].get("component")) for event_id in span if event_id in events_by_id}
        if len(components) > 1 and group["classification"].strip().lower() in generic:
            errors.append("false_merge_candidate")
        normalized.append({**group, "source_span": span})
    all_claimed = claimed + ungrouped
    if len(all_claimed) != len(set(all_claimed)): errors.append("duplicate_candidate_accounting")
    if set(all_claimed) != ids: errors.append("candidate_recall_failed")
    return {"accepted": not errors, "errors": sorted(set(errors)), "groups": normalized if not errors else [], "ungrouped": ungrouped if not errors else []}


def final_accounting(events: list[dict[str, Any]], initial: list[dict[str, Any]], groups: list[dict[str, Any]], ungrouped: list[str], *, fallback: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped = {event_id: group["group_id"] for group in groups for event_id in group["source_span"]}
    final: list[dict[str, Any]] = []
    for row in initial:
        disposition = row["disposition"]
        output = dict(row)
        if disposition == "model_candidate":
            if fallback: output["disposition"] = "fallback_observed"
            elif row["event_id"] in grouped: output.update({"disposition": "semantic_group", "group_id": grouped[row["event_id"]]})
            else: output["disposition"] = "semantic_ungrouped"
        final.append(output)
    counts = Counter(row["disposition"] for row in final)
    summary = {"observed_total": len(events), "model_candidate_total": sum(row["disposition"] == "model_candidate" for row in initial), "semantically_grouped_total": counts["semantic_group"], "semantic_ungrouped_total": counts["semantic_ungrouped"], "structural_continuation_total": counts["structural_continuation"], "deterministically_excluded_total": counts["deterministically_excluded"], "policy_blocked_total": counts["policy_blocked"], "unclassified_observed_total": counts["unclassified_observed"], "fallback_observed_total": counts["fallback_observed"], "fully_accounted": len(final) == len(events) and len({row["event_id"] for row in final}) == len(events)}
    return final, summary
