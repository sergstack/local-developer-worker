from datetime import date

import pytest

from local_developer_worker.session_log import append_event, iter_events
from local_developer_worker.telemetry import telemetry_event
from local_developer_worker import portfolio


def test_session_log_refuses_symlink_partition(tmp_path):
    target = tmp_path / "outside.jsonl"
    partition = tmp_path / f"{date.today().isoformat()}.jsonl"
    partition.symlink_to(target)
    event = telemetry_event({"tool": "doctor", "status": "success", "run_id": "RUN-safe"})

    with pytest.raises(OSError):
        append_event(event, tmp_path)

    assert not target.exists()


def test_session_log_reader_does_not_follow_symlink_partition(tmp_path):
    target = tmp_path / "outside.jsonl"
    target.write_text('{"raw_log":"must-not-be-read"}\n')
    partition = tmp_path / f"{date.today().isoformat()}.jsonl"
    partition.symlink_to(target)

    events, invalid = iter_events(tmp_path)

    assert events == []
    assert invalid == 1


def test_portfolio_state_cannot_escape_repo_index(tmp_path, monkeypatch):
    target = tmp_path / "tracked-looking.py"
    monkeypatch.setenv("LDW_PORTFOLIO_STATE", str(target))

    output = portfolio.portfolio_verify({"only": "AI-02"})

    assert output["status"] == "partial"
    assert output["warnings"] == [{"code": "portfolio_state_not_saved"}]
    assert not target.exists()
