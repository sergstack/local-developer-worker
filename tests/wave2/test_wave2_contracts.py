from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from local_developer_worker.tools import context_pack, evidence_build


ROOT = Path(__file__).parents[2]


def _schema(name: str):
    return Draft202012Validator(json.loads((ROOT / "schemas" / name).read_text()))


def _lineage_item():
    return {
        "evidence_type": "test_status",
        "source_tool": "test_result_parser",
        "source_run_id": "RUN-tests",
        "source_type": "tool_result",
        "source_path": "tests/test_app.py",
        "event_id": None,
        "test_run_id": "TEST-RUN-1",
        "git_observation_id": None,
        "origin": "observed",
        "value": {"status": "incomplete"},
    }


def test_context_and_expansion_payloads_validate_public_schema(tmp_path):
    files = [{"path": "src/app.py", "size_bytes": 100}, {"path": "src/config.py", "size_bytes": 80}]
    initial = context_pack({"repository_root": str(tmp_path), "task": "inspect", "files": files, "target_files": ["src/app.py"]})
    expanded = context_pack({
        "mode": "expand",
        "repository_root": str(tmp_path),
        "previous_run_id": initial["run_id"],
        "previous_package": initial,
        "requested_paths": ["src/config.py"],
        "reason": "Missing imported configuration",
        "files": files,
    })
    validator = _schema("context_package.schema.json")
    validator.validate(initial["data"])
    validator.validate(expanded["data"])


def test_complete_evidence_payload_validates_public_schema(tmp_path):
    output = evidence_build({
        "repository_root": str(tmp_path),
        "task": "resume",
        "repository_state": {},
        "observed_log_events": [],
        "observed_test_results": [],
        "file_inventory": [],
        "evidence_items": [_lineage_item()],
        "next_bounded_action": "inspect src/app.py",
    })
    assert output["status"] == "success"
    _schema("evidence_package.schema.json").validate(output["data"]["evidence_package"])


def test_wave2_corpus_is_frozen_and_has_exact_required_case_contract():
    corpus = json.loads((ROOT / "fixtures" / "wave2" / "reference_corpus.json").read_text())
    required = {
        "case_id", "repository_fixture_or_root", "task", "explicit_target_files", "critical_files",
        "allowed_related_files", "acceptable_exclusions", "forbidden_sensitive_files", "required_symbols",
        "required_tests", "expected_git_facts", "expected_observed_failures", "expansion_requests",
        "source_type", "sensitive_content_present",
    }
    assert corpus["frozen"] is True
    assert len(corpus["cases"]) == 15
    assert len({case["case_id"] for case in corpus["cases"]}) == 15
    assert all(required <= set(case) for case in corpus["cases"])
    assert all(case["sensitive_content_present"] is False for case in corpus["cases"])
    assert all(set(case["critical_files"]).isdisjoint(case["forbidden_sensitive_files"]) for case in corpus["cases"])
