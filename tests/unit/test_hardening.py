import json

from local_developer_worker.tools import context_pack, evidence_build, parse_log, parse_tests


def test_log_parser_is_deterministic_and_strips_ansi():
    payload = {"text": "\x1b[31mERROR boom\x1b[0m\r\n\nunknown\r\n"}
    first, second = parse_log(payload), parse_log(payload)
    assert first == second
    assert first["data"]["events"][0]["message"] == "ERROR boom"
    assert first["data"]["events"][0]["raw_line_start"] == 1


def test_test_parser_never_promotes_exit_zero_without_evidence():
    assert parse_tests({"text": "quiet output", "exit_code": 0, "command_observed": True})["data"]["run_status"] == "unknown"


def test_test_parser_observes_pytest_nonpass_states():
    output = parse_tests({"text": "SKIPPED tests/a.py::a\nXFAIL tests/a.py::b\nXPASS tests/a.py::c", "exit_code": 0, "command_observed": True})
    assert [item["status"] for item in output["data"]["tests"]] == ["skipped", "xfailed", "xpassed"]
    assert output["data"]["run_status"] == "unknown"


def test_test_parser_classifies_timeout_and_collection_error():
    assert parse_tests({"text": "test session timeout", "exit_code": 124, "command_observed": True})["data"]["run_status"] == "timeout"
    assert parse_tests({"text": "ERROR collecting tests/test_bad.py", "exit_code": 2, "command_observed": True})["data"]["run_status"] == "error"


def test_evidence_rejects_bad_source_reference():
    output = evidence_build({"task": "x", "repository_state": {}, "observed_log_events": [{"event_id": "EV-1", "raw_hash": "bad", "raw_line_start": 2, "raw_line_end": 1}], "observed_test_results": [], "file_inventory": []})
    assert output["status"] == "invalid_input"


def test_context_packer_deduplicates_paths_and_has_reasons():
    output = context_pack({"files": [{"path": "src/a.py"}, {"path": "src/a.py"}], "named_files": ["src/a.py"]})
    assert output["data"]["included_files"][0]["path"] == "src/a.py"
    assert output["data"]["excluded_candidates"][0]["reason"] == "duplicate_path"


def test_context_mode_keeps_visible_exclusions_and_expansion_handle():
    output = context_pack({"mode": "context", "task": "fix", "files": [{"path": "src/a.py"}, {"path": "docs/a.md"}], "named_files": ["src/a.py"], "failure_event_ids": ["EV-002"]})["data"]
    assert output["mode"] == "context"
    assert output["relevant_files"] == ["src/a.py"]
    assert output["relevant_failures"] == ["EV-002"]
    assert output["contract_version"] == "2.0.0"
    assert output["excluded_files"][0]["path"] == "docs/a.md"
    assert output["excluded_files"][0]["reason_code"] == "not_selected"


def test_context_packer_includes_standard_pytest_layout():
    output = context_pack({"files": [{"path": "src/parser.py"}, {"path": "tests/test_parser.py"}], "named_files": ["src/parser.py"]})["data"]
    reasons = {item["path"]: item["reasons"] for item in output["included_files"]}
    assert reasons["tests/test_parser.py"] == ["related_test"]


def test_context_packer_includes_nested_pytest_layout():
    output = context_pack({"files": [{"path": "src/pkg/mod.py"}, {"path": "tests/pkg/test_mod.py"}], "named_files": ["src/pkg/mod.py"]})["data"]
    reasons = {item["path"]: item["reasons"] for item in output["included_files"]}
    assert reasons["tests/pkg/test_mod.py"] == ["related_test"]


def test_context_packer_includes_matching_test_path_without_prefix():
    output = context_pack({"files": [{"path": "src/pkg/mod.py"}, {"path": "tests/pkg/mod.py"}], "named_files": ["src/pkg/mod.py"]})["data"]
    reasons = {item["path"]: item["reasons"] for item in output["included_files"]}
    assert reasons["tests/pkg/mod.py"] == ["related_test"]


def test_context_packer_does_not_match_vendor_source_by_stem():
    output = context_pack({"files": [{"path": "tests/test_config.py"}], "named_files": ["vendor/third_party/config.py"]})["data"]
    excluded = {item["path"]: item["reason"] for item in output["excluded_candidates"]}
    assert excluded["tests/test_config.py"] == "no_deterministic_signal"


def test_context_packer_does_not_match_ambiguous_source_stem():
    output = context_pack({"files": [{"path": "src/b/utils.py"}, {"path": "tests/test_utils.py"}], "changed_files": ["src/a/utils.py"]})["data"]
    excluded = {item["path"]: item["reason"] for item in output["excluded_candidates"]}
    assert excluded["tests/test_utils.py"] == "no_deterministic_signal"


def test_context_packer_does_not_match_documentation_by_stem():
    output = context_pack({"files": [{"path": "tests/test_date.py"}], "named_files": ["docs/date.py"]})["data"]
    excluded = {item["path"]: item["reason"] for item in output["excluded_candidates"]}
    assert excluded["tests/test_date.py"] == "no_deterministic_signal"
