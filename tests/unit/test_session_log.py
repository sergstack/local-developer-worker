from datetime import date

from local_developer_worker.session_log import append_event, iter_events
from local_developer_worker.telemetry import SAFE_FIELDS, telemetry_event


def _event(tool="doctor"):
    return telemetry_event(
        {
            "tool": tool,
            "input_bytes": 2,
            "output_bytes": 100,
            "latency_ms": 3,
            "status": "success",
            "fallback_used": False,
            "context_reduction": None,
            "run_id": "RUN-observed",
            "raw_log": "TOKEN=must-not-survive",
        }
    )


def test_telemetry_event_uses_exact_safe_fields():
    event = _event()
    assert set(event) == SAFE_FIELDS
    assert set(event) == {
        "tool",
        "input_bytes",
        "output_bytes",
        "latency_ms",
        "status",
        "fallback_used",
        "context_reduction",
        "run_id",
    }


def test_session_log_appends_without_overwriting(tmp_path):
    partition = append_event(_event("doctor"), tmp_path, event_date=date(2026, 8, 2))
    first_bytes = partition.read_bytes()
    append_event(_event("git facts"), tmp_path, event_date=date(2026, 8, 2))

    assert partition.read_bytes().startswith(first_bytes)
    events, invalid = iter_events(tmp_path)
    assert invalid == 0
    assert [event["tool"] for event in events] == ["doctor", "git facts"]
