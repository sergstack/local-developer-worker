from __future__ import annotations

import re
from typing import Any

from .contracts import canonical_json, result

SAFE_FIELDS = {
    "tool",
    "input_bytes",
    "output_bytes",
    "latency_ms",
    "status",
    "fallback_used",
    "context_reduction",
    "run_id",
    "error_code",
}
LEGACY_SAFE_FIELDS = SAFE_FIELDS - {"error_code"}
KNOWN_ERROR_CODES = frozenset(
    {
        "capability_disabled",
        "cases_must_be_list",
        "conflicting_cli_option",
        "duplicate_evidence_id",
        "evidence_items_must_be_list",
        "evidence_package_required",
        "files_must_be_list",
        "gate_reconciliation_failed",
        "generated_document_drift",
        "git_unavailable",
        "input_size_exceeded",
        "internal_error",
        "invalid_context_input",
        "invalid_evidence_reference",
        "invalid_json",
        "invalid_output_schema",
        "invalid_policy",
        "invalid_portfolio",
        "invalid_previous_package",
        "invalid_repository_root",
        "invalid_semantic_candidates",
        "invalid_telemetry_range",
        "invalid_telemetry_records",
        "invalid_usefulness_mark",
        "legacy_implicit_repository_root",
        "non_loopback_inference_endpoint",
        "observed_log_events_must_be_list",
        "parsed_log_events_required",
        "portfolio_state_not_saved",
        "previous_package_link_required",
        "repository_root_not_allowed",
        "requested_paths_must_be_list",
        "semantic_code_artifact_prohibited",
        "semantic_disabled",
        "semantic_fallback_used",
        "semantic_must_be_boolean",
        "semantic_runtime_not_configured",
        "telemetry_mark_write_failed",
        "text_must_be_string",
        "text_required",
        "timeout_before_execution",
        "unclassified_observed_excessive",
        "unknown_lines",
        "unsafe_or_invalid_log_events",
        "unsafe_or_unsupported_evidence",
        "unsupported_context_mode",
    }
)
USEFULNESS_MARK_FIELDS = {"run_id", "mark"}
USEFULNESS_MARKS = {"helped", "not_helped", "unclear"}
RUN_ID_PATTERN = re.compile(r"RUN-[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")


def valid_telemetry_event(event: Any) -> bool:
    if not isinstance(event, dict) or set(event) != SAFE_FIELDS:
        return False
    integer_fields = ("input_bytes", "output_bytes", "latency_ms")
    if any(not isinstance(event[field], int) or isinstance(event[field], bool) or event[field] < 0 for field in integer_fields):
        return False
    if not all(isinstance(event[field], str) for field in ("tool", "status", "run_id")):
        return False
    if not isinstance(event["fallback_used"], bool):
        return False
    error_code = event["error_code"]
    if error_code is not None and (not isinstance(error_code, str) or error_code not in KNOWN_ERROR_CODES):
        return False
    reduction = event["context_reduction"]
    return reduction is None or isinstance(reduction, (int, float)) and not isinstance(reduction, bool)


def telemetry_event(values: dict[str, Any]) -> dict[str, Any]:
    """Return a privacy-preserving telemetry record without raw inputs or prompts."""
    context_reduction = values.get("context_reduction")
    error_code = values.get("error_code")
    return {
        "tool": str(values.get("tool", "unknown")),
        "input_bytes": int(values.get("input_bytes", 0)),
        "output_bytes": int(values.get("output_bytes", 0)),
        "latency_ms": int(values.get("latency_ms", 0)),
        "status": str(values.get("status", "unknown")),
        "fallback_used": bool(values.get("fallback_used", False)),
        "context_reduction": context_reduction if isinstance(context_reduction, (int, float)) else None,
        "run_id": str(values.get("run_id", "")),
        "error_code": error_code if isinstance(error_code, str) and error_code in KNOWN_ERROR_CODES else None,
    }


def telemetry_error_code(output: Any) -> str | None:
    """Return only the first known public error or warning code."""
    if not isinstance(output, dict):
        return None
    for field in ("errors", "warnings"):
        rows = output.get(field)
        if not isinstance(rows, list) or not rows:
            continue
        first = rows[0]
        code = first.get("code") if isinstance(first, dict) else None
        if isinstance(code, str) and code in KNOWN_ERROR_CODES:
            return code
    return None


def normalize_telemetry_event(event: Any) -> dict[str, Any] | None:
    """Normalize pre-TEL-04 records without weakening new-write validation."""
    if valid_telemetry_event(event):
        return dict(event)
    if isinstance(event, dict) and set(event) == LEGACY_SAFE_FIELDS:
        normalized = {**event, "error_code": None}
        return normalized if valid_telemetry_event(normalized) else None
    return None


def valid_usefulness_mark(record: Any) -> bool:
    return (
        isinstance(record, dict)
        and set(record) == USEFULNESS_MARK_FIELDS
        and isinstance(record["run_id"], str)
        and RUN_ID_PATTERN.fullmatch(record["run_id"]) is not None
        and record["mark"] in USEFULNESS_MARKS
    )


def usefulness_mark(values: dict[str, Any]) -> dict[str, str]:
    record = {"run_id": str(values.get("run_id", "")), "mark": str(values.get("mark", ""))}
    if not valid_usefulness_mark(record):
        raise ValueError("invalid usefulness mark")
    return record


def valid_session_record(record: Any) -> bool:
    return normalize_telemetry_event(record) is not None or valid_usefulness_mark(record)


def telemetry_mark(payload: dict[str, Any]) -> dict[str, Any]:
    from .session_log import append_event

    raw = canonical_json(payload)
    try:
        record = usefulness_mark(payload)
    except ValueError as exc:
        return result(
            "telemetry_mark",
            "session_log",
            raw,
            {},
            status="invalid_input",
            errors=[{"code": "invalid_usefulness_mark", "detail": str(exc)}],
        )
    try:
        append_event(record)
    except OSError:
        return result(
            "telemetry_mark",
            "session_log",
            raw,
            {"recorded": False},
            status="partial",
            errors=[{"code": "telemetry_mark_write_failed"}],
        )
    return result("telemetry_mark", "session_log", raw, {"recorded": True, **record})


def telemetry_summary(payload: dict[str, Any]) -> dict[str, Any]:
    from .session_log import iter_records

    raw = canonical_json(payload)
    try:
        records, invalid_records = iter_records(
            payload.get("journal_root"),
            date_from=payload.get("date_from"),
            date_to=payload.get("date_to"),
        )
    except (OSError, ValueError) as exc:
        return result(
            "telemetry_summary",
            "session_log",
            raw,
            {},
            status="invalid_input",
            errors=[{"code": "invalid_telemetry_range", "detail": str(exc)}],
        )
    events = [record for record in records if valid_telemetry_event(record)]
    mark_records = [record for record in records if valid_usefulness_mark(record)]
    latest_marks = {record["run_id"]: record["mark"] for record in mark_records}
    mark_counts = {mark: sum(value == mark for value in latest_marks.values()) for mark in sorted(USEFULNESS_MARKS)}
    marked_runs = len(latest_marks)
    context_events = [
        event
        for event in events
        if event["tool"] == "context pack/context" and isinstance(event["context_reduction"], (int, float))
    ]
    fallback_count = sum(bool(event["fallback_used"]) for event in events)
    event_count = len(events)
    error_code_counts = {
        code: sum(event["error_code"] == code for event in events)
        for code in sorted({event["error_code"] for event in events if event["error_code"] is not None})
    }
    data = {
        "event_count": event_count,
        "input_bytes": sum(int(event["input_bytes"]) for event in events),
        "output_bytes": sum(int(event["output_bytes"]) for event in events),
        "context_pack_context_calls": len(context_events),
        "average_context_reduction": (
            round(sum(float(event["context_reduction"]) for event in context_events) / len(context_events), 4)
            if context_events
            else None
        ),
        "fallback_count": fallback_count,
        "fallback_ratio": round(fallback_count / event_count, 4) if event_count else 0.0,
        "error_code_counts": error_code_counts,
        "automated_evidence_or_report_calls": sum(
            event["tool"] in {"evidence build", "report summarize"} for event in events
        ),
        "usefulness": {
            "mark_records": len(mark_records),
            "marked_runs": marked_runs,
            "counts": mark_counts,
            "ratios": {
                mark: round(count / marked_runs, 4) if marked_runs else 0.0
                for mark, count in mark_counts.items()
            },
        },
        "invalid_records": invalid_records,
        "date_from": payload.get("date_from"),
        "date_to": payload.get("date_to"),
    }
    return result(
        "telemetry_summary",
        "session_log",
        raw,
        data,
        status="partial" if invalid_records else "success",
        warnings=[{"code": "invalid_telemetry_records", "count": invalid_records}] if invalid_records else [],
    )
