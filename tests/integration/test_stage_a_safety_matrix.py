from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import validate

from local_developer_worker import cli
from local_developer_worker.contracts import sha256


ROOT = Path(__file__).parents[2]
TOOL_RESULT_SCHEMA = json.loads((ROOT / "schemas" / "tool_result.schema.json").read_text())


def _run(args: list[str], payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", *args],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        check=False,
    )


@pytest.mark.parametrize(
    ("args", "payload"),
    [
        (["doctor"], {}),
        (["log", "parse"], {"text": "INFO ready\nopaque"}),
        (["test", "parse"], {"text": "PASSED tests/test_ok.py::test_ok", "exit_code": 0, "command_observed": True}),
        (["git", "facts"], {"repository_root": str(ROOT)}),
        (["files", "inventory"], {"repository_root": str(ROOT), "max_file_size": 1}),
        (
            ["evidence", "build"],
            {"task": "inspect", "repository_state": {}, "observed_log_events": [], "observed_test_results": [], "file_inventory": []},
        ),
        (["context", "pack"], {"files": [{"path": "src/a.py"}], "named_files": ["src/a.py"]}),
        (
            ["report", "summarize"],
            {"evidence_package": {"repository_state": {}, "observed_test_results": [], "missing_evidence": [], "warnings": []}},
        ),
        (["benchmark", "run"], {"cases": []}),
    ],
    ids=["doctor", "log-parse", "test-parse", "git-facts", "files-inventory", "evidence-build", "context-pack", "report-summarize", "benchmark-run"],
)
def test_gate_schema_valid_output_for_all_nine_commands(args, payload):
    completed = _run(args, payload)
    assert completed.returncode == 0
    assert completed.stderr == ""
    validate(instance=json.loads(completed.stdout), schema=TOOL_RESULT_SCHEMA)


def test_gate_log_parse_accounts_for_every_input_line_without_silent_loss():
    text = "INFO ready\n\nopaque\nERROR failed"
    output = json.loads(_run(["log", "parse"], {"text": text}).stdout)
    accounting = output["data"]["line_accounting"]
    events = output["data"]["events"]

    assert accounting["input_lines"] == len(text.splitlines()) == len(events)
    assert accounting["input_lines"] == sum(
        accounting[state]
        for state in ("parsed", "part_of_event", "unknown_event", "unsupported_format", "parse_failed")
    )
    assert [event["raw_line_start"] for event in events] == [1, 2, 3, 4]
    assert [event["raw_hash"] for event in events] == [sha256(line) for line in text.splitlines()]
    assert events[2]["message"] == "opaque"
    assert events[2]["parse_status"] == "unknown_event"
    assert accounting["unknown_event"] == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"text": "", "exit_code": 0, "command_observed": True},
        {"text": "PASSED tests/test_ok.py::test_ok", "exit_code": None, "command_observed": True},
        {"text": "PASSED tests/test_ok.py::test_ok", "exit_code": 0, "command_observed": False},
        {"text": "PASSED tests/test_ok.py::test_ok\nkilled", "exit_code": 137, "command_observed": True},
    ],
    ids=["zero-exit-no-result", "missing-exit", "command-unobserved", "interrupted"],
)
def test_gate_test_parse_cannot_claim_passed_without_observed_completed_pass(payload):
    output = json.loads(_run(["test", "parse"], payload).stdout)
    assert output["data"]["run_status"] != "passed"


def test_gate_test_parse_marks_exit_137_with_truncated_output_incomplete():
    truncated_pytest_output = """============================= test session starts ==============================
collected 2 items

tests/test_worker.py PASSED tests/test_worker.py::test_first
tests/test_worker.py"""
    output = json.loads(
        _run(
            ["test", "parse"],
            {
                "text": truncated_pytest_output,
                "exit_code": 137,
                "command_observed": True,
            },
        ).stdout
    )

    assert output["status"] == "partial"
    assert output["data"]["exit_code"] == 137
    assert output["data"]["run_status"] == "incomplete"
    assert output["data"]["run_status"] != "passed"


def test_gate_report_summarize_emits_only_evidence_backed_lists():
    evidence = {
        "repository_state": {
            "changed_files": ["src/observed.py"],
            "command_evidence": ["pytest tests/observed.py"],
            "working_tree_clean": False,
        },
        "observed_test_results": [{"test_id": "tests/observed.py::test_case", "status": "failed"}],
        "missing_evidence": ["rollback_command"],
        "warnings": [{"code": "observed_warning"}],
        "content_hash": "synthetic-evidence-hash",
    }
    data = json.loads(_run(["report", "summarize"], {"evidence_package": evidence}).stdout)["data"]

    assert data["files_changed"] == evidence["repository_state"]["changed_files"]
    assert data["commands_observed"] == evidence["repository_state"]["command_evidence"]
    assert data["tests_observed"] == evidence["observed_test_results"]
    assert data["missing_checks"] == evidence["missing_evidence"]
    assert data["warnings"] == evidence["warnings"]
    assert data["acceptance_evidence"] == {"content_hash": evidence["content_hash"]}


def test_gate_report_without_observed_test_results_makes_no_test_claim():
    evidence = {
        "repository_state": {"changed_files": [], "command_evidence": []},
        "missing_evidence": ["observed_test_results"],
        "warnings": [],
        "content_hash": "synthetic-evidence-without-tests",
    }
    data = json.loads(_run(["report", "summarize"], {"evidence_package": evidence}).stdout)["data"]

    assert data["tests_observed"] == []
    assert data["missing_checks"] == ["observed_test_results"]
    assert "passed" not in data["summary"].lower()


def test_gate_cli_output_is_byte_identical_for_identical_input():
    payload = {"text": "INFO deterministic\nopaque", "source": "synthetic.log"}
    first = _run(["log", "parse"], payload)
    second = _run(["log", "parse"], payload)
    assert first.returncode == second.returncode == 0
    assert first.stdout.encode() == second.stdout.encode()
    assert first.stderr.encode() == second.stderr.encode()


def _invoke_main(monkeypatch, capsys, policy: Path, handler):
    monkeypatch.setitem(cli.COMMANDS, ("doctor",), handler)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"policy_path": str(policy)})))
    return_code = cli.main(["doctor"])
    return return_code, json.loads(capsys.readouterr().out)


def test_gate_invalid_schema_fallback_is_reachable_and_observable(tmp_path, monkeypatch, capsys):
    policy = tmp_path / "policy.toml"
    policy.write_text("[fallback]\non_invalid_schema = 'schema-fallback'\n")
    return_code, output = _invoke_main(monkeypatch, capsys, policy, lambda payload: {"invalid": True})

    assert return_code == 2
    assert output["status"] == "internal_error"
    assert output["errors"] == [{"code": "invalid_output_schema"}]
    assert output["data"]["fallback"] == "schema-fallback"


def test_gate_internal_error_fallback_is_reachable_and_observable(tmp_path, monkeypatch, capsys):
    policy = tmp_path / "policy.toml"
    policy.write_text("[fallback]\non_internal_error = 'internal-fallback'\n")

    def fail(_payload):
        raise RuntimeError("synthetic internal failure")

    return_code, output = _invoke_main(monkeypatch, capsys, policy, fail)
    assert return_code == 2
    assert output["status"] == "internal_error"
    assert output["errors"][0]["code"] == "internal_error"
    assert output["data"]["fallback"] == "internal-fallback"
