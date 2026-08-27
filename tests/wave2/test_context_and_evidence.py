from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from local_developer_worker.tools import context_pack, evidence_build


ROOT = Path(__file__).parents[2]


def _files():
    return [
        {"path": "src/app.py", "size_bytes": 100},
        {"path": "src/config.py", "size_bytes": 80},
        {"path": "tests/test_app.py", "size_bytes": 60},
        {"path": "docs/notes.md", "size_bytes": 200},
        {"path": "build/app.generated.py", "size_bytes": 300, "generated_candidate": True},
        {"path": "credentials.fake", "size_bytes": 40, "potentially_sensitive": True},
        {"path": "assets/blob.bin", "size_bytes": 500, "binary": True},
        {"path": "ignored/cache.txt", "size_bytes": 600, "ignored_by_policy": True},
    ]


def _lineage_item(evidence_type: str, value: object, **overrides):
    item = {
        "evidence_type": evidence_type,
        "source_tool": "structured_log_parser",
        "source_run_id": "RUN-source",
        "source_type": "tool_result",
        "source_path": "src/app.py",
        "event_id": "EV-000001",
        "test_run_id": None,
        "git_observation_id": None,
        "origin": "observed",
        "value": value,
    }
    item.update(overrides)
    return item


def _evidence_payload(root: Path, items: list[dict]):
    return {
        "repository_root": str(root),
        "task": "Resume bounded investigation",
        "repository_state": {},
        "observed_log_events": [],
        "observed_test_results": [],
        "file_inventory": [{"path": "src/app.py"}],
        "evidence_items": items,
        "current_observed_state": "one observed failure",
        "next_bounded_action": "inspect src/config.py",
    }


def test_public_cli_requires_explicit_allowed_repository_root():
    for command, payload in [
        (["context", "pack"], {"files": []}),
        (["evidence", "build"], {"task": "x"}),
    ]:
        completed = subprocess.run(
            [sys.executable, "-m", "local_developer_worker.cli", *command],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "LDW_TELEMETRY_DISABLED": "1"},
            check=False,
        )
        output = json.loads(completed.stdout)
        assert output["status"] == "policy_blocked"
        assert output["errors"] == [{"code": "repository_root_not_allowed"}]


def test_context_selection_is_traceable_and_exclusions_are_visible(tmp_path):
    output = context_pack({
        "repository_root": str(tmp_path),
        "task": "Inspect application",
        "files": _files(),
        "target_files": ["src/app.py"],
        "changed_files": ["src/config.py"],
        "related_tests": ["tests/test_app.py"],
    })
    data = output["data"]
    included = {item["path"]: item for item in data["included_files"]}
    excluded = {item["path"]: item for item in data["excluded_files"]}

    assert data["contract_version"] == "2.0.0"
    assert included["src/app.py"]["relevance_status"] == "explicit"
    assert included["src/config.py"]["relevance_status"] == "candidate"
    assert included["tests/test_app.py"]["relevance_status"] == "deterministic_dependency"
    assert all(item["selection_reason"] and item["evidence_source"] for item in included.values())
    assert excluded["credentials.fake"]["reason_code"] == "sensitive_path"
    assert excluded["assets/blob.bin"]["reason_code"] == "binary"
    assert excluded["ignored/cache.txt"]["reason_code"] == "ignored_by_policy"
    assert excluded["build/app.generated.py"]["reason_code"] == "generated_not_required"
    assert excluded["docs/notes.md"]["reason_code"] == "not_selected"


def test_context_blocks_all_minimum_sensitive_path_classes_without_contents(tmp_path):
    sensitive_paths = [
        ".env", ".repo_index/diagnostic.json", "auth_store.json",
        "provider_raw_response.json", "tokens.txt", "private-key.pem",
    ]
    output = context_pack({
        "repository_root": str(tmp_path),
        "files": [{"path": path, "size_bytes": 10} for path in sensitive_paths],
        "target_files": sensitive_paths,
    })
    assert output["status"] == "unsupported"
    assert {item["path"] for item in output["data"]["excluded_files"]} == set(sensitive_paths)
    assert {item["reason_code"] for item in output["data"]["excluded_files"]} == {"sensitive_path"}


def test_context_blocks_outside_root_and_symlink_escape(tmp_path):
    outside = tmp_path.parent / "outside-wave2.txt"
    outside.write_text("sanitized")
    (tmp_path / "link.py").symlink_to(outside)
    output = context_pack({
        "repository_root": str(tmp_path),
        "files": [{"path": "../outside.py", "size_bytes": 10}, {"path": "link.py", "size_bytes": 10}],
        "target_files": ["../outside.py", "link.py"],
    })
    excluded = {item["path"]: item["reason_code"] for item in output["data"]["excluded_files"]}
    assert excluded["../outside.py"] == "outside_repository_root"
    assert excluded["link.py"] == "outside_repository_root"
    assert output["status"] == "unsupported"


def test_context_limit_and_low_benefit_are_visible(tmp_path):
    limited = context_pack({
        "repository_root": str(tmp_path),
        "files": _files()[:3],
        "target_files": ["src/app.py", "src/config.py"],
        "max_context_files": 1,
    })["data"]
    assert limited["budget"] == {"max_context_files": 1, "consumed": 1}
    assert any(item["reason_code"] == "over_context_limit" for item in limited["excluded_files"])

    low_benefit = context_pack({
        "repository_root": str(tmp_path),
        "files": [{"path": "src/app.py", "size_bytes": 100}],
        "target_files": ["src/app.py"],
    })["data"]
    assert low_benefit["selection_status"] == "low_benefit_bypass"
    assert low_benefit["metrics"]["context_reduction"] == 0.0


def test_context_excludes_nonexplicit_identical_content_with_canonical_reason(tmp_path):
    same_hash = "a" * 64
    output = context_pack({
        "repository_root": str(tmp_path),
        "files": [
            {"path": "src/canonical.py", "size_bytes": 100, "hash": same_hash},
            {"path": "docs/copy.md", "size_bytes": 100, "hash": same_hash},
        ],
        "target_files": ["src/canonical.py"],
        "changed_files": ["docs/copy.md"],
    })["data"]

    assert [item["path"] for item in output["included_files"]] == ["src/canonical.py"]
    assert output["excluded_files"] == [{
        "path": "docs/copy.md", "included": False, "reason": "redundant_content",
        "reason_code": "redundant_content", "policy_rule": "identical_content_hash_to:src/canonical.py",
    }]


def test_context_retains_distinct_or_explicit_candidates_despite_similar_metadata(tmp_path):
    output = context_pack({
        "repository_root": str(tmp_path),
        "files": [
            {"path": "src/contract.py", "size_bytes": 100, "hash": "a" * 64},
            {"path": "docs/contract.md", "size_bytes": 100, "hash": "b" * 64},
            {"path": "docs/verbatim-copy.md", "size_bytes": 100, "hash": "a" * 64},
        ],
        "target_files": ["src/contract.py", "docs/verbatim-copy.md"],
        "changed_files": ["docs/contract.md"],
    })["data"]

    assert {item["path"] for item in output["included_files"]} == {
        "src/contract.py", "docs/contract.md", "docs/verbatim-copy.md",
    }
    assert not any(item["reason_code"] == "redundant_content" for item in output["excluded_files"])


def test_context_returns_reproducible_python_symbol_slice_with_imports(tmp_path):
    source = tmp_path / "src" / "sample.py"
    source.parent.mkdir()
    source.write_text("import os\n\nCONSTANT = 1\n\ndef helper():\n    return CONSTANT\n\ndef target():\n    return helper()\n")
    output = context_pack({"repository_root": str(tmp_path), "files": [{"path": "src/sample.py", "size_bytes": source.stat().st_size}], "target_files": ["src/sample.py"], "target_symbols": ["target"]})["data"]

    slice_ = output["source_slices"][0]
    assert slice_["path"] == "src/sample.py"
    assert slice_["mode"] == "structural_slice"
    assert slice_["symbols"] == ["target"]
    assert slice_["ranges"] == [{"line_start": 1, "line_end": 1}, {"line_start": 3, "line_end": 3}, {"line_start": 5, "line_end": 6}, {"line_start": 8, "line_end": 9}]
    assert "import os" in slice_["content"] and "def helper" in slice_["content"] and "def target" in slice_["content"]


def test_context_slice_keeps_decorators_constants_and_nested_definitions(tmp_path):
    source = tmp_path / "src" / "decorated.py"
    source.parent.mkdir()
    source.write_text("VALUE = 3\n\ndef decorate(fn):\n    return fn\n\n@decorate\ndef target():\n    def nested():\n        return VALUE\n    return nested()\n")
    data = context_pack({"repository_root": str(tmp_path), "files": [{"path": "src/decorated.py", "size_bytes": source.stat().st_size}], "target_files": ["src/decorated.py"], "target_symbols": ["target"]})["data"]
    content = data["source_slices"][0]["content"]
    assert "VALUE = 3" in content and "@decorate" in content and "def nested" in content


def test_context_slice_keeps_class_and_reexport_context(tmp_path):
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("from shared import Contract as PublicContract\n\nclass Service:\n    contract = PublicContract\n")
    data = context_pack({"repository_root": str(tmp_path), "files": [{"path": "src/service.py", "size_bytes": source.stat().st_size}], "target_files": ["src/service.py"], "target_symbols": ["Service"]})["data"]
    content = data["source_slices"][0]["content"]
    assert "from shared import Contract as PublicContract" in content and "class Service" in content


def test_context_slice_falls_back_for_invalid_python(tmp_path):
    source = tmp_path / "src" / "broken.py"
    source.parent.mkdir()
    source.write_text("def broken(:\n")
    data = context_pack({"repository_root": str(tmp_path), "files": [{"path": "src/broken.py", "size_bytes": source.stat().st_size}], "target_files": ["src/broken.py"], "target_symbols": ["broken"]})["data"]
    assert data["source_slices"] == [{"path": "src/broken.py", "mode": "whole_file_fallback", "reason": "unsupported_python_syntax", "symbols": [], "ranges": []}]


def test_unsupported_candidate_is_visible_not_silently_dropped(tmp_path):
    output = context_pack({
        "repository_root": str(tmp_path),
        "files": [],
        "target_files": ["unknown/layout.xyz"],
    })
    assert output["status"] == "unsupported"
    assert output["data"]["excluded_files"] == [{
        "path": "unknown/layout.xyz",
        "included": False,
        "reason": "unsupported",
        "reason_code": "unsupported",
        "policy_rule": "candidate_not_in_inventory",
    }]


def test_expansion_links_previous_package_and_reapplies_policy(tmp_path):
    base = context_pack({
        "repository_root": str(tmp_path),
        "files": _files(),
        "target_files": ["src/app.py"],
    })
    expanded = context_pack({
        "mode": "expand",
        "repository_root": str(tmp_path),
        "previous_run_id": base["run_id"],
        "previous_package": base,
        "requested_paths": ["src/config.py", "credentials.fake", "../outside.py"],
        "reason": "Imported by selected target",
        "files": _files() + [{"path": "../outside.py", "size_bytes": 10}],
    })
    data = expanded["data"]
    assert data["previous_run_id"] == base["run_id"]
    assert [item["path"] for item in data["added_files"]] == ["src/config.py"]
    assert len([item for item in data["included_files"] if item["path"] == "src/app.py"]) == 1
    blocked = {item["path"]: item["reason_code"] for item in data["still_excluded"]}
    assert blocked["credentials.fake"] == "sensitive_path"
    assert blocked["../outside.py"] == "outside_repository_root"
    assert expanded["status"] == "partial"


def test_expansion_rejects_unlinked_previous_package(tmp_path):
    output = context_pack({
        "mode": "expand",
        "repository_root": str(tmp_path),
        "previous_run_id": "RUN-wrong",
        "previous_package": {"run_id": "RUN-other", "data": {}},
        "requested_paths": [],
        "files": [],
    })
    assert output["status"] == "invalid_input"
    assert output["errors"][0]["code"] == "previous_package_link_required"


def test_evidence_lineage_and_resume_state_are_complete(tmp_path):
    items = [
        _lineage_item("log_event", {"level": "error"}),
        _lineage_item(
            "test_status",
            {"status": "incomplete"},
            source_tool="test_result_parser",
            source_run_id="RUN-tests",
            test_run_id="TEST-RUN-1",
            event_id=None,
        ),
        _lineage_item(
            "git_state",
            {"working_tree_clean": False},
            source_tool="git_facts_collector",
            source_run_id="RUN-git",
            git_observation_id="GIT-OBS-1",
            event_id=None,
        ),
        _lineage_item(
            "error_group",
            {"group_id": "SG-ONE"},
            source_tool="semantic_log_clustering",
            source_run_id="RUN-model",
            origin="model-derived-candidate",
        ),
    ]
    first = evidence_build(_evidence_payload(tmp_path, items))
    second = evidence_build(_evidence_payload(tmp_path, items))
    package = first["data"]["evidence_package"]

    assert first == second
    assert first["status"] == "success"
    assert package["contract_version"] == "2.0.0"
    assert package["lineage_complete"] is True
    assert package["test_statuses"][0]["source_tool"] == "test_result_parser"
    assert package["git_state"][0]["source_tool"] == "git_facts_collector"
    assert package["model_derived_candidates"][0]["origin"] == "model-derived-candidate"
    resume = package["resume_state"]
    assert resume["objective"] == "Resume bounded investigation"
    assert resume["current_observed_state"] == "one observed failure"
    assert resume["files_already_considered"] == ["src/app.py"]
    assert resume["tests_actually_observed"]
    assert resume["known_failures"]
    assert resume["next_bounded_action"] == "inspect src/config.py"


def test_evidence_never_invents_test_or_git_authority(tmp_path):
    invalid_test = _lineage_item("test_status", {"status": "passed"}, source_tool="pytest", test_run_id=None)
    invalid_git = _lineage_item("git_state", {"changed_files": []}, source_tool="unknown", git_observation_id=None)
    output = evidence_build(_evidence_payload(tmp_path, [invalid_test, invalid_git]))
    package = output["data"]["evidence_package"]
    assert output["status"] == "partial"
    assert package["lineage_complete"] is False
    assert any("test_status_requires_ldw_test_parse" in finding for finding in package["lineage_findings"])
    assert any("git_state_requires_ldw_git_facts_or_user" in finding for finding in package["lineage_findings"])


def test_evidence_blocks_sensitive_lineage_and_root_cause_claims(tmp_path):
    sensitive = _lineage_item("file", {"hash": "sanitized"}, source_path="credentials.fake")
    root_cause = _lineage_item("root_cause", "invented")
    for item in (sensitive, root_cause):
        output = evidence_build(_evidence_payload(tmp_path, [item]))
        assert output["status"] == "invalid_input"
        assert output["errors"][0]["code"] == "unsafe_or_unsupported_evidence"


def test_evidence_without_observed_tests_remains_visible_not_run(tmp_path):
    output = evidence_build(_evidence_payload(tmp_path, [_lineage_item("log_event", {"level": "error"})]))
    package = output["data"]["evidence_package"]
    assert output["status"] == "partial"
    assert "tests: NOT RUN" in package["missing_evidence"]
    assert package["resume_state"]["tests_actually_observed"] == []
