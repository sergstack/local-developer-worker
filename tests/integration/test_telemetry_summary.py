from datetime import date
import json
import os
import subprocess
import sys
from pathlib import Path

from local_developer_worker.session_log import append_event, iter_events
from local_developer_worker.telemetry import telemetry_event, telemetry_summary


def _event(tool, input_bytes, output_bytes, *, fallback=False, reduction=None):
    return telemetry_event(
        {
            "tool": tool,
            "input_bytes": input_bytes,
            "output_bytes": output_bytes,
            "latency_ms": 5,
            "status": "success",
            "fallback_used": fallback,
            "context_reduction": reduction,
            "run_id": f"RUN-{tool}",
        }
    )


def test_telemetry_summary_reports_real_aggregates_and_date_filter(tmp_path):
    append_event(_event("doctor", 10, 20), tmp_path, event_date=date(2026, 8, 1))
    append_event(_event("context pack/context", 100, 40, reduction=0.6), tmp_path, event_date=date(2026, 8, 2))
    append_event(_event("report summarize", 30, 15, fallback=True), tmp_path, event_date=date(2026, 8, 2))

    data = telemetry_summary({"journal_root": str(tmp_path), "date_from": "2026-08-02", "date_to": "2026-08-02"})["data"]

    assert data["event_count"] == 2
    assert data["input_bytes"] == 130
    assert data["output_bytes"] == 55
    assert data["context_pack_context_calls"] == 1
    assert data["average_context_reduction"] == 0.6
    assert data["fallback_count"] == 1
    assert data["fallback_ratio"] == 0.5
    assert data["automated_evidence_or_report_calls"] == 1


def test_cli_appends_one_safe_event_without_changing_stdout(tmp_path):
    root = Path(__file__).parents[2]
    completed = subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", "doctor"],
        input="{}",
        text=True,
        capture_output=True,
        cwd=root,
        env={
            **os.environ,
            "PYTHONPATH": str(root / "src"),
            "LDW_SESSION_LOG_DIR": str(tmp_path),
            "LDW_TELEMETRY_FORCE": "1",
        },
        check=False,
    )
    output = json.loads(completed.stdout)
    events, invalid = iter_events(tmp_path)

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert output["status"] == "success"
    assert invalid == 0
    assert len(events) == 1
    assert events[0]["tool"] == "doctor"
    assert events[0]["output_bytes"] == len(completed.stdout.encode())


def test_cli_records_invalid_json_without_recording_raw_input(tmp_path):
    root = Path(__file__).parents[2]
    completed = subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", "doctor"],
        input="{invalid-json",
        text=True,
        capture_output=True,
        cwd=root,
        env={
            **os.environ,
            "PYTHONPATH": str(root / "src"),
            "LDW_SESSION_LOG_DIR": str(tmp_path),
            "LDW_TELEMETRY_FORCE": "1",
        },
        check=False,
    )
    events, invalid = iter_events(tmp_path)

    assert completed.returncode == 2
    assert invalid == 0
    assert len(events) == 1
    assert events[0]["status"] == "invalid_input"
    assert "invalid-json" not in json.dumps(events[0])
