from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

from .contracts import stable_hash

INFERENCE_EVENT_FIELDS = (
    "event_id",
    "level",
    "component",
    "message",
    "exception_type",
    "source_file",
    "source_line",
    "raw_line_start",
    "raw_line_end",
    "raw_hash",
    "parse_status",
    "origin",
)
SENSITIVE_TEXT = re.compile(
    r"(?:AKIA[0-9A-Z]{16}|-----BEGIN .*PRIVATE KEY-----|(?:password|token|secret|api[_-]?key)\s*[:=])",
    re.I,
)
SEMANTIC_GROUP_FIELDS = {"group_id", "pattern", "classification", "source_span", "confidence", "origin", "needs_review"}


def build_inference_payload(events: list[dict[str, Any]]) -> dict[str, Any]:
    sanitized = []
    seen = set()
    for event in events:
        event_id = event.get("event_id")
        source_file = event.get("source_file")
        message = event.get("message")
        if not isinstance(event_id, str) or event_id in seen or not isinstance(message, str):
            raise ValueError("invalid_or_duplicate_event")
        if SENSITIVE_TEXT.search(message):
            raise ValueError("sensitive_event_content")
        if source_file is not None:
            source_path = PurePosixPath(source_file)
            if source_path.is_absolute() or ".." in source_path.parts:
                raise ValueError("unsafe_source_path")
        row = {key: event.get(key) for key in INFERENCE_EVENT_FIELDS if key in event}
        row["origin"] = "observed"
        sanitized.append(row)
        seen.add(event_id)
    return {"events": sanitized, "payload_hash": stable_hash(sanitized)}


def _path_disagreement(group: dict[str, Any], events_by_id: dict[str, dict[str, Any]]) -> bool:
    for event_id in group["source_span"]:
        source = str(events_by_id[event_id].get("source_file") or "").lower()
        name = PurePosixPath(source).name
        if PurePosixPath(source).suffix in {".sh", ".bash"} and ("deploy" in name or "prod" in name):
            return group["classification"] != "deployment_script"
    return False


def validate_candidate_response(
    events: list[dict[str, Any]],
    response: dict[str, Any],
    *,
    ground_truth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    events_by_id = {event.get("event_id"): event for event in events if isinstance(event, dict)}
    errors = []
    if len(events_by_id) != len(events) or None in events_by_id:
        return {"accepted": False, "errors": ["invalid_event_set"], "groups": [], "excluded": []}
    groups = response.get("groups") if isinstance(response, dict) else None
    excluded = response.get("excluded") if isinstance(response, dict) else None
    if not isinstance(groups, list) or not isinstance(excluded, list):
        return {"accepted": False, "errors": ["invalid_candidate_shape"], "groups": [], "excluded": []}
    normalized = []
    claimed = []
    for group in groups:
        if not isinstance(group, dict):
            errors.append("invalid_group")
            continue
        spans = group.get("source_span")
        confidence = group.get("confidence")
        if (
            set(group) != SEMANTIC_GROUP_FIELDS
            or not isinstance(group.get("group_id"), str)
            or not re.fullmatch(r"SG-[A-Z0-9_-]+", group["group_id"])
            or not isinstance(group.get("needs_review"), bool)
        ):
            errors.append("invalid_group_contract")
        if not isinstance(spans, list) or not spans or not all(isinstance(value, str) for value in spans):
            errors.append("invalid_source_span")
            continue
        if any(event_id not in events_by_id for event_id in spans):
            errors.append("invented_source")
        if len(spans) != len(set(spans)):
            errors.append("duplicate_source_span")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            errors.append("confidence_out_of_bounds")
        if group.get("origin") != "model-derived":
            errors.append("invalid_origin")
        required_text = all(isinstance(group.get(key), str) and group[key] for key in ("pattern", "classification"))
        if not required_text:
            errors.append("invalid_group_contract")
        claimed.extend(spans)
        if not errors or all(event_id in events_by_id for event_id in spans):
            normalized_group = {
                "group_id": group.get("group_id"),
                "pattern": group.get("pattern"),
                "classification": group.get("classification"),
                "source_span": spans,
                "confidence": confidence,
                "origin": group.get("origin"),
                "needs_review": bool(group.get("needs_review")) or (
                    all(event_id in events_by_id for event_id in spans) and _path_disagreement(group, events_by_id)
                ),
            }
            normalized.append(normalized_group)
    excluded_ids = []
    for row in excluded:
        if not isinstance(row, dict) or set(row) != {"event_id", "reason"} or not isinstance(row.get("event_id"), str) or not isinstance(row.get("reason"), str) or not row["reason"]:
            errors.append("invalid_exclusion")
            continue
        if row["event_id"] not in events_by_id:
            errors.append("invented_source")
        excluded_ids.append(row["event_id"])
    if len(claimed) != len(set(claimed)) or set(claimed).intersection(excluded_ids):
        errors.append("duplicate_event_accounting")
    if set(claimed) | set(excluded_ids) != set(events_by_id):
        errors.append("source_span_recall_failed")
    if ground_truth is not None:
        expected_groups = {frozenset(group["members"]) for group in ground_truth["groups"]}
        observed_groups = {frozenset(group.get("source_span", [])) for group in groups if isinstance(group, dict)}
        if expected_groups != observed_groups:
            errors.append("ground_truth_grouping_mismatch")
        membership = {event_id: index for index, group in enumerate(groups) if isinstance(group, dict) for event_id in group.get("source_span", [])}
        if any(membership.get(left) == membership.get(right) for left, right in ground_truth["must_remain_separate"]):
            errors.append("required_separation_failed")
    return {
        "accepted": not errors,
        "errors": sorted(set(errors)),
        "groups": normalized if not errors else [],
        "excluded": excluded if not errors else [],
    }


def evaluate_candidate_response(
    events: list[dict[str, Any]],
    response: dict[str, Any] | None,
    *,
    failure: str | None = None,
    ground_truth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if failure or response is None:
        validation = {"accepted": False, "errors": [failure or "missing_candidate_response"]}
    else:
        validation = validate_candidate_response(events, response, ground_truth=ground_truth)
    if not validation["accepted"]:
        observed = [{**event, "origin": "observed"} for event in events]
        return {
            "status": "partial",
            "fallback_used": True,
            "fallback_reason": validation["errors"],
            "observed_events": observed,
            "semantic_groups": [],
        }
    return {
        "status": "success",
        "fallback_used": False,
        "fallback_reason": [],
        "observed_events": [{**event, "origin": "observed"} for event in events],
        "semantic_groups": validation["groups"],
    }
