from local_developer_worker.tools import context_pack, parse_log, parse_tests


def test_log_parser_accounts_for_every_line():
    output = parse_log({"text": "INFO ready\nERROR failed\nopaque"})
    accounting = output["data"]["line_accounting"]
    assert accounting["input_lines"] == sum(accounting[key] for key in ("parsed", "part_of_event", "unknown_event", "unsupported_format", "parse_failed"))


def test_interrupted_test_is_not_passed():
    output = parse_tests({"text": "PASSED tests/test_x.py::test_x", "exit_code": 137, "command_observed": True})
    assert output["data"]["run_status"] == "incomplete"
    assert output["data"]["tests"][0]["status"] == "passed"


def test_context_packer_explains_exclusion():
    output = context_pack({"files": [{"path": "src/a.py"}, {"path": ".env", "potentially_sensitive": True}], "named_files": ["src/a.py"]})
    assert output["data"]["included_files"][0]["reasons"] == ["explicitly_named"]
    assert output["data"]["excluded_candidates"][0]["reason"] == "sensitive_blocked"


def test_context_packer_includes_direct_import():
    output = context_pack({"files": [{"path": "src/a.py"}, {"path": "src/b.py"}], "named_files": ["src/a.py"], "import_edges": {"src/a.py": ["src/b.py"]}})
    included = {item["path"]: item["reasons"] for item in output["data"]["included_files"]}
    assert included["src/b.py"] == ["direct_import"]
