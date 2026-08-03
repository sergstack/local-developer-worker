from local_developer_worker.telemetry import SAFE_FIELDS, telemetry_event


def test_telemetry_drops_raw_content():
    event = telemetry_event({"tool": "log", "latency_ms": 3, "raw_log": "TOKEN=synthetic"})
    assert event["tool"] == "log"
    assert "raw_log" not in event
    assert set(event) == SAFE_FIELDS
    assert event["context_reduction"] is None
