import copy
import json
import subprocess
import sys

from local_developer_worker import portfolio


def _isolate_state(tmp_path, monkeypatch):
    monkeypatch.setattr(portfolio, "STATE_ROOT", tmp_path)
    monkeypatch.setattr(portfolio, "DEFAULT_STATE", tmp_path / "state.json")


def test_portfolio_verify_only_ai02_completes_recorded_decision_with_artifacts(tmp_path, monkeypatch):
    _isolate_state(tmp_path, monkeypatch)
    output = portfolio.portfolio_verify({"only": "AI-02"})
    view = output["data"]["portfolio"]

    assert view["item_count"] == 20
    assert len(view["items"]) == 20
    ai02 = next(item for item in view["items"] if item["id"] == "AI-02")
    assert ai02["status"] == "complete"
    assert [row["check_id"] for row in ai02["evidence"]] == ["AI-02-agents-rule", "AI-02-doctor-reminder"]
    assert all(row["status"] == "passed" for row in ai02["evidence"])
    assert view["next_resumable_command"] == "ldw portfolio verify --only SA-01"


def test_ai02_without_decision_returns_to_waiting_for_input(tmp_path, monkeypatch):
    _isolate_state(tmp_path, monkeypatch)
    registry = copy.deepcopy(portfolio.load_registry())
    registry["items"][17].pop("decision")
    registry_path = tmp_path / "gate_registry.json"
    registry_path.write_text(json.dumps(registry))
    monkeypatch.setattr(portfolio, "DEFAULT_REGISTRY", registry_path)

    output = portfolio.portfolio_verify({"only": "AI-02"})
    ai02 = next(item for item in output["data"]["portfolio"]["items"] if item["id"] == "AI-02")

    assert ai02["status"] == "waiting_for_input"
    assert ai02["evidence"][0]["check_id"] == "AI-02-options"


def test_ai02_status_without_decision_does_not_reuse_completed_state(tmp_path, monkeypatch):
    _isolate_state(tmp_path, monkeypatch)
    completed = portfolio.portfolio_verify({"only": "AI-02"})
    assert next(item for item in completed["data"]["portfolio"]["items"] if item["id"] == "AI-02")["status"] == "complete"

    registry = copy.deepcopy(portfolio.load_registry())
    registry["items"][17].pop("decision")
    registry_path = tmp_path / "gate_registry.json"
    registry_path.write_text(json.dumps(registry))
    monkeypatch.setattr(portfolio, "DEFAULT_REGISTRY", registry_path)

    status = portfolio.portfolio_status({})
    ai02 = next(item for item in status["data"]["portfolio"]["items"] if item["id"] == "AI-02")
    assert ai02["status"] == "waiting_for_input"


def test_portfolio_verifier_continues_after_one_gate_failure(tmp_path, monkeypatch):
    _isolate_state(tmp_path, monkeypatch)
    registry = portfolio.load_registry()
    nodes = {node for item in registry["items"] for node in item["evidence_test_ids"]}
    failing = registry["items"][0]["evidence_test_ids"][0]

    monkeypatch.setattr(portfolio, "_collect_all_nodes", lambda timeout: nodes)
    monkeypatch.setattr(
        portfolio,
        "_run_pytest",
        lambda node_id, collect_only, timeout: {
            "return_code": 1 if node_id == failing and not collect_only else 0,
            "stdout_sha256": "observed",
            "stderr_sha256": "observed",
            "elapsed_ms": 0,
            **({} if collect_only else {"test_parser": {"status": "success", "run_status": "failed" if node_id == failing else "passed"}}),
        },
    )
    output = portfolio.portfolio_verify({})
    items = output["data"]["portfolio"]["items"]

    assert len(items) == 20
    assert items[0]["status"] == "judge_revise"
    assert all(item["status"] == "complete" for item in items[1:16])
    assert items[17]["status"] == "complete"
    assert items[18]["id"] == "AI-03"


def test_portfolio_status_marks_completed_evidence_stale(tmp_path, monkeypatch):
    _isolate_state(tmp_path, monkeypatch)
    monkeypatch.setattr(portfolio, "_collect_all_nodes", lambda timeout: set())
    portfolio.portfolio_verify({"only": "AI-04"})
    monkeypatch.setattr(portfolio, "_workspace_fingerprint", lambda registry: "changed")

    view = portfolio.portfolio_status({})["data"]["portfolio"]
    ai04 = next(item for item in view["items"] if item["id"] == "AI-04")
    assert ai04["status"] == "judge_revise"


def test_every_declared_gate_node_is_exactly_collected():
    registry = portfolio.load_registry()
    declared = {node for item in registry["items"] if item["category"] == "gate" for node in item["evidence_test_ids"]}
    collected = portfolio._collect_all_nodes(60)
    assert declared <= collected


def test_portfolio_prefers_executable_repository_venv_for_pytest(tmp_path, monkeypatch):
    interpreter = tmp_path / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("#!/bin/sh\n")
    interpreter.chmod(0o700)
    monkeypatch.setattr(portfolio, "ROOT", tmp_path)

    assert portfolio._pytest_interpreter() == str(interpreter)


def test_portfolio_falls_back_to_its_own_interpreter_without_repository_venv(tmp_path, monkeypatch):
    monkeypatch.setattr(portfolio, "ROOT", tmp_path)

    assert portfolio._pytest_interpreter() == sys.executable


def test_portfolio_execution_uses_test_parser_not_return_code_alone(monkeypatch):
    monkeypatch.setattr(portfolio, "_pytest_interpreter", lambda: sys.executable)
    monkeypatch.setattr(
        portfolio.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, "PASSED tests/unit/test_example.py::test_ok\n", ""
        ),
    )

    observed = portfolio._run_pytest("tests/unit/test_example.py::test_ok", collect_only=False, timeout=1)

    assert observed["test_parser"]["status"] == "success"
    assert observed["test_parser"]["run_status"] == "passed"


def test_portfolio_rejects_zero_exit_code_without_a_confirmed_parsed_pass(tmp_path, monkeypatch):
    _isolate_state(tmp_path, monkeypatch)
    registry = portfolio.load_registry()
    nodes = {node for item in registry["items"] for node in item["evidence_test_ids"]}
    monkeypatch.setattr(portfolio, "_collect_all_nodes", lambda timeout: nodes)
    monkeypatch.setattr(
        portfolio,
        "_run_pytest",
        lambda node_id, collect_only, timeout: {
            "return_code": 0,
            "stdout_sha256": "observed",
            "stderr_sha256": "observed",
            "elapsed_ms": 0,
            **({} if collect_only else {"test_parser": {"status": "partial", "run_status": "unknown"}}),
        },
    )

    output = portfolio.portfolio_verify({"only": "SA-01"})
    sa01 = next(item for item in output["data"]["portfolio"]["items"] if item["id"] == "SA-01")

    assert sa01["status"] == "judge_revise"
