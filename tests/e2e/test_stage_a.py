from local_developer_worker.tools import context_pack, evidence_build, parse_log, parse_tests, report_summarize


def test_facts_only_pipeline_preserves_observed_test_status():
    log = parse_log({"text": "ERROR database unavailable"})["data"]["events"]
    tests = parse_tests({"text": "PASSED tests/test_a.py::test_a", "exit_code": 137, "command_observed": True})["data"]
    package = evidence_build({"task": "investigate", "repository_state": {"changed_files": ["src/a.py"], "command_evidence": []}, "observed_log_events": log, "observed_test_results": [tests], "file_inventory": [], "missing_evidence": ["final pytest summary"]})["data"]["evidence_package"]
    report = report_summarize({"evidence_package": package})["data"]
    assert report["files_changed"] == ["src/a.py"]
    assert report["tests_observed"][0]["run_status"] == "incomplete"
    assert context_pack({"files": [{"path": "src/a.py"}], "changed_files": ["src/a.py"]})["data"]["included_files"]
