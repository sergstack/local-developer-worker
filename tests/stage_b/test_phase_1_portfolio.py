from local_developer_worker import stage_b_portfolio


def test_phase_1_runner_routes_observed_output_through_test_parser(monkeypatch):
    observed = {}

    class Completed:
        stdout = "PASSED tests/example.py::test_example\n"
        stderr = ""
        returncode = 0

    def parse(payload):
        observed.update(payload)
        return {"data": {"run_status": "passed", "tests": [{"test_id": "tests/example.py::test_example"}]}}

    monkeypatch.setattr(stage_b_portfolio.subprocess, "run", lambda *args, **kwargs: Completed())
    monkeypatch.setattr(stage_b_portfolio, "parse_tests", parse)

    evidence = stage_b_portfolio._run_test("tests/example.py::test_example")

    assert observed["command_observed"] is True
    assert evidence["run_status"] == "passed"
    assert evidence["observed_test_count"] == 1


def test_phase_1_runner_continues_after_failed_item(monkeypatch):
    registry = stage_b_portfolio.load_phase_1_registry()
    failing = registry["items"][0]["evidence_test_ids"][0]

    def run(node, timeout):
        passed = node != failing
        return {
            "test_id": node,
            "run_status": "passed" if passed else "failed",
            "exit_code": 0 if passed else 1,
            "observed_test_ids": [node] if passed else [],
            "observed_test_count": 1 if passed else 0,
            "evidence_hash": "observed",
        }

    monkeypatch.setattr(stage_b_portfolio, "_run_test", run)
    output = stage_b_portfolio.run_phase_1_portfolio()

    assert output["portfolio_size"] == 10
    assert output["items"][0]["status"] == "judge_revise"
    assert all(item["status"] == "complete" for item in output["items"][1:])
    assert output["portfolio_acceptance"] == "phase_1_partial"
    assert output["next_resumable_action"] == {
        "item_id": "POLICY-01",
        "command": "PYTHONPATH=src python scripts/run_stage_b_portfolio.py",
    }
