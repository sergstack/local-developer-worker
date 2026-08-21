from datetime import date
import json
import os
import subprocess
import sys
from pathlib import Path

from local_developer_worker.session_log import append_event, iter_events, iter_records
from local_developer_worker.telemetry import codex_run_event, telemetry_event, telemetry_summary, usefulness_mark


def _event(tool, input_bytes, output_bytes, *, fallback=False, reduction=None, error_code=None):
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
            "error_code": error_code,
        }
    )


def test_telemetry_summary_reports_real_aggregates_and_date_filter(tmp_path):
    append_event(_event("doctor", 10, 20), tmp_path, event_date=date(2026, 8, 1))
    append_event(_event("context pack/context", 100, 40, reduction=0.6), tmp_path, event_date=date(2026, 8, 2))
    append_event(
        _event("report summarize", 30, 15, fallback=True, error_code="semantic_fallback_used"),
        tmp_path,
        event_date=date(2026, 8, 2),
    )

    data = telemetry_summary({"journal_root": str(tmp_path), "date_from": "2026-08-02", "date_to": "2026-08-02"})["data"]

    assert data["event_count"] == 2
    assert data["input_bytes"] == 130
    assert data["output_bytes"] == 55
    assert data["context_pack_context_calls"] == 1
    assert data["average_context_reduction"] == 0.6
    assert data["fallback_count"] == 1
    assert data["fallback_ratio"] == 0.5
    assert data["error_code_counts"] == {"semantic_fallback_used": 1}
    assert data["automated_evidence_or_report_calls"] == 1
    assert data["usefulness"] == {
        "mark_records": 0,
        "marked_runs": 0,
        "counts": {"helped": 0, "not_helped": 0, "unclear": 0},
        "ratios": {"helped": 0.0, "not_helped": 0.0, "unclear": 0.0},
    }


def test_telemetry_summary_aggregates_latest_mark_per_run_id(tmp_path):
    for run_id, mark in [
        ("RUN-one", "helped"),
        ("RUN-two", "not_helped"),
        ("RUN-three", "unclear"),
        ("RUN-two", "helped"),
    ]:
        append_event(usefulness_mark({"run_id": run_id, "mark": mark}), tmp_path, event_date=date(2026, 8, 2))

    data = telemetry_summary({"journal_root": str(tmp_path)})["data"]

    assert data["event_count"] == 0
    assert data["usefulness"] == {
        "mark_records": 4,
        "marked_runs": 3,
        "counts": {"helped": 2, "not_helped": 0, "unclear": 1},
        "ratios": {"helped": 0.6667, "not_helped": 0.0, "unclear": 0.3333},
    }


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
    assert events[0]["error_code"] is None


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
    assert events[0]["error_code"] == "invalid_json"
    assert "invalid-json" not in json.dumps(events[0])


def test_cli_appends_manual_usefulness_mark(tmp_path):
    root = Path(__file__).parents[2]
    completed = subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", "telemetry", "mark", "RUN-observed", "helped"],
        input="{}",
        text=True,
        capture_output=True,
        cwd=root,
        env={
            **os.environ,
            "PYTHONPATH": str(root / "src"),
            "LDW_SESSION_LOG_DIR": str(tmp_path),
            "LDW_TELEMETRY_DISABLED": "1",
        },
        check=False,
    )
    output = json.loads(completed.stdout)
    records, invalid = iter_records(tmp_path)

    assert completed.returncode == 0
    assert output["status"] == "success"
    assert output["data"] == {"recorded": True, "run_id": "RUN-observed", "mark": "helped"}
    assert invalid == 0
    assert records == [{"run_id": "RUN-observed", "mark": "helped"}]


def test_telemetry_summary_aggregates_privacy_safe_codex_events(tmp_path):
    append_event(
        codex_run_event(
            {
                "run_id": "RUN-codex",
                "profile": "frontier",
                "model_alias": "large",
                "effort": "high",
                "terminal_status": "pass",
                "verification_status": "passed",
                "fallback_count": 1,
                "escalation_count": 2,
                "input_tokens": 10,
                "cached_input_tokens": 4,
                "output_tokens": 3,
                "reasoning_output_tokens": None,
            }
        ),
        tmp_path,
        event_date=date(2026, 8, 2),
    )
    data = telemetry_summary({"journal_root": str(tmp_path)})["data"]["codex"]
    assert data == {
        "run_count": 1,
        "profile_counts": {"balanced": 0, "efficient": 0, "frontier": 1},
        "terminal_status_counts": {"blocked": 0, "failed": 0, "pass": 1},
        "fallback_count": 1,
        "escalation_count": 2,
        "tokens": {"input_tokens": 10, "cached_input_tokens": 4, "output_tokens": 3, "reasoning_output_tokens": 0},
    }
