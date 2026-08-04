import json
from datetime import date

from local_developer_worker.session_log import append_event, iter_events, iter_records
from local_developer_worker.telemetry import SAFE_FIELDS, telemetry_event, usefulness_mark


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
        "error_code",
    }


def test_session_log_appends_without_overwriting(tmp_path):
    partition = append_event(_event("doctor"), tmp_path, event_date=date(2026, 8, 2))
    first_bytes = partition.read_bytes()
    append_event(_event("git facts"), tmp_path, event_date=date(2026, 8, 2))

    assert partition.read_bytes().startswith(first_bytes)
    events, invalid = iter_events(tmp_path)
    assert invalid == 0
    assert [event["tool"] for event in events] == ["doctor", "git facts"]


def test_session_log_appends_usefulness_mark_without_overwriting_telemetry(tmp_path):
    partition = append_event(_event("doctor"), tmp_path, event_date=date(2026, 8, 2))
    first_bytes = partition.read_bytes()
    append_event(usefulness_mark({"run_id": "RUN-observed", "mark": "helped"}), tmp_path, event_date=date(2026, 8, 2))

    assert partition.read_bytes().startswith(first_bytes)
    records, invalid = iter_records(tmp_path)
    events, event_invalid = iter_events(tmp_path)
    assert invalid == event_invalid == 0
    assert records[-1] == {"run_id": "RUN-observed", "mark": "helped"}
    assert [event["tool"] for event in events] == ["doctor"]


def test_session_log_normalizes_legacy_event_error_code_to_null(tmp_path):
    legacy = _event()
    del legacy["error_code"]
    partition = tmp_path / "2026-08-02.jsonl"
    partition.write_text(json.dumps(legacy) + "\n", encoding="utf-8")

    events, invalid = iter_events(tmp_path)

    assert invalid == 0
    assert events[0]["error_code"] is None
