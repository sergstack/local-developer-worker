from __future__ import annotations

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
}


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
    reduction = event["context_reduction"]
    return reduction is None or isinstance(reduction, (int, float)) and not isinstance(reduction, bool)


def telemetry_event(values: dict[str, Any]) -> dict[str, Any]:
    """Return a privacy-preserving telemetry record without raw inputs or prompts."""
    context_reduction = values.get("context_reduction")
    return {
        "tool": str(values.get("tool", "unknown")),
        "input_bytes": int(values.get("input_bytes", 0)),
        "output_bytes": int(values.get("output_bytes", 0)),
        "latency_ms": int(values.get("latency_ms", 0)),
        "status": str(values.get("status", "unknown")),
        "fallback_used": bool(values.get("fallback_used", False)),
        "context_reduction": context_reduction if isinstance(context_reduction, (int, float)) else None,
        "run_id": str(values.get("run_id", "")),
    }


def telemetry_summary(payload: dict[str, Any]) -> dict[str, Any]:
    from .session_log import iter_events

    raw = canonical_json(payload)
    try:
        events, invalid_records = iter_events(
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
    context_events = [
        event
        for event in events
        if event["tool"] == "context pack/context" and isinstance(event["context_reduction"], (int, float))
    ]
    fallback_count = sum(bool(event["fallback_used"]) for event in events)
    event_count = len(events)
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
        "automated_evidence_or_report_calls": sum(
            event["tool"] in {"evidence build", "report summarize"} for event in events
        ),
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
