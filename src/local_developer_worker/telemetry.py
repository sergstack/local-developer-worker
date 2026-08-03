from __future__ import annotations

from typing import Any

from .contracts import stable_hash

SAFE_FIELDS = {"tool", "version", "reason_called", "input_bytes", "output_bytes", "input_items", "output_items", "latency_ms", "status", "accepted", "rejected", "fallback_used", "context_reduction", "token_proxy", "run_id"}


def telemetry_event(values: dict[str, Any]) -> dict[str, Any]:
    """Return a privacy-preserving telemetry record without raw inputs or prompts."""
    event = {key: values[key] for key in SAFE_FIELDS if key in values}
    event["event_hash"] = stable_hash(event)
    return event
