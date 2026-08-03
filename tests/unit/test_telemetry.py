from local_developer_worker.telemetry import telemetry_event


def test_telemetry_drops_raw_content():
    event = telemetry_event({"tool": "log", "latency_ms": 3, "raw_log": "TOKEN=synthetic"})
    assert event["tool"] == "log"
    assert "raw_log" not in event
    assert "event_hash" in event
