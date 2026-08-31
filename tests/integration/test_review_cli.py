import json
import os
import subprocess
import sys
from pathlib import Path

from jsonschema import validate

def test_review_build_cli_returns_derived_deterministic_package():
    root = Path(__file__).parents[2]
    environment = {**os.environ, "PYTHONPATH": str(root / "src"), "LDW_TELEMETRY_DISABLED": "1"}
    payload = {
        "contract_version": "1.0.0",
        "objective": "Compile a bounded review package.",
        "scope": {
            "scope_id": "SCOPE_001", "change_size": "local",
            "changed_components": [{"component_id": "COMPONENT_REVIEW", "kind": "source"}],
            "declared_boundaries": ["review"], "contract_change": False,
        },
        "git_facts": {
            "source_tool": "git_facts_collector", "source_run_id": "RUN_GIT_001",
            "working_tree_clean": False, "changed_component_ids": ["COMPONENT_REVIEW"],
        },
        "evidence": {
            "source_tool": "evidence_package_builder", "source_run_id": "RUN_EVIDENCE_001",
            "content_hash": "a" * 64, "lineage_complete": True,
            "observed_evidence_refs": ["EV_TEST_001"], "candidate_evidence_refs": [],
            "missing_evidence_ids": [], "unknown_ids": [],
        },
        "required_checks": [{
            "check_id": "CHECK_TEST_001", "check_type": "test", "status": "passed",
            "source_tool": "test_result_parser", "evidence_refs": ["EV_TEST_001"],
        }],
    }

    completed = subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", "review", "build"],
        input=json.dumps(payload), text=True, capture_output=True, cwd=root, env=environment, check=False,
    )

    assert completed.returncode == 0
    output = json.loads(completed.stdout)
    tool_result_schema = json.loads((root / "schemas" / "tool_result.schema.json").read_text())
    validate(instance=output, schema=tool_result_schema)
    assert output["tool"] == "review_package_builder"
    assert output["status"] == "success"
    assert output["data"]["review_profile"] == "local"
    assert output["data"]["authority"]["model_invoked"] is False
    assert output["data"]["derived_view_plan"]["rendering"] == "not_in_p0"


def test_review_build_cli_v1_1_returns_ledger_without_renderer_or_model():
    root = Path(__file__).parents[2]
    environment = {**os.environ, "PYTHONPATH": str(root / "src"), "LDW_TELEMETRY_DISABLED": "1"}
    payload = {
        "contract_version": "1.1.0", "objective": "Compile review ledger.",
        "scope": {"scope_id": "SCOPE_002", "change_size": "local", "changed_components": [{"component_id": "COMPONENT_REVIEW", "kind": "contract"}], "declared_boundaries": ["review"], "contract_change": True},
        "git_facts": {"source_tool": "git_facts_collector", "source_run_id": "RUN_GIT_002", "working_tree_clean": False, "changed_component_ids": ["COMPONENT_REVIEW"]},
        "evidence": {"source_tool": "evidence_package_builder", "source_run_id": "RUN_EVIDENCE_002", "content_hash": "a" * 64, "lineage_complete": True, "observed_evidence_refs": ["EV_TEST_002"], "candidate_evidence_refs": [], "missing_evidence_ids": [], "unknown_ids": []},
        "required_checks": [{"check_id": "CHECK_TEST_002", "check_type": "test", "status": "passed", "source_tool": "test_result_parser", "evidence_refs": ["EV_TEST_002"]}],
        "contract_comparison": {"availability": "available", "unavailable_reason_id": None, "baseline": {"contract_id": "CONTRACT_BASE", "version_label": "1.0.0", "content_hash": "b" * 64}, "candidate": {"contract_id": "CONTRACT_NEXT", "version_label": "1.1.0", "content_hash": "c" * 64}, "added_field_ids": ["FIELD_LEDGER"], "removed_field_ids": [], "changed_field_ids": []},
    }

    completed = subprocess.run([sys.executable, "-m", "local_developer_worker.cli", "review", "build"], input=json.dumps(payload), text=True, capture_output=True, cwd=root, env=environment, check=False)

    assert completed.returncode == 0
    output = json.loads(completed.stdout)
    assert output["data"]["contract_version"] == "1.1.0"
    assert output["data"]["evidence_ledger"]["derived"] is True
    assert output["data"]["contract_delta"]["compatibility_assessment"] == "not_in_p1"
    assert output["data"]["authority"]["model_invoked"] is False
    assert output["data"]["derived_view_plan"]["rendering"] == "not_in_p1"


def test_review_build_cli_v1_2_preserves_canonical_ldw_run_ids():
    root = Path(__file__).parents[2]
    environment = {**os.environ, "PYTHONPATH": str(root / "src"), "LDW_TELEMETRY_DISABLED": "1"}
    payload = {
        "contract_version": "1.2.0", "objective": "Preserve canonical LDW run identifiers.",
        "scope": {"scope_id": "SCOPE_003", "change_size": "local", "changed_components": [{"component_id": "COMPONENT_REVIEW", "kind": "contract"}], "declared_boundaries": ["review"], "contract_change": True},
        "git_facts": {"source_tool": "git_facts_collector", "source_run_id": "RUN-f93fa534e6572dce", "working_tree_clean": False, "changed_component_ids": ["COMPONENT_REVIEW"]},
        "evidence": {"source_tool": "evidence_package_builder", "source_run_id": "RUN-0a03b39836c4fb48", "content_hash": "a" * 64, "lineage_complete": True, "observed_evidence_refs": ["EV_TEST_003"], "candidate_evidence_refs": [], "missing_evidence_ids": [], "unknown_ids": []},
        "required_checks": [{"check_id": "CHECK_TEST_003", "check_type": "test", "status": "passed", "source_tool": "test_result_parser", "evidence_refs": ["EV_TEST_003"]}],
        "contract_comparison": None,
    }

    completed = subprocess.run([sys.executable, "-m", "local_developer_worker.cli", "review", "build"], input=json.dumps(payload), text=True, capture_output=True, cwd=root, env=environment, check=False)

    assert completed.returncode == 0
    output = json.loads(completed.stdout)
    assert output["status"] == "success"
    assert output["data"]["contract_version"] == "1.2.0"
    assert output["data"]["evidence_export"]["git_source_run_id"] == "RUN-f93fa534e6572dce"


def test_review_render_cli_emits_derived_markdown_only():
    root = Path(__file__).parents[2]
    environment = {**os.environ, "PYTHONPATH": str(root / "src"), "LDW_TELEMETRY_DISABLED": "1"}
    build_payload = {
        "contract_version": "1.0.0", "objective": "Render a review package.",
        "scope": {"scope_id": "SCOPE_RENDER", "change_size": "local", "changed_components": [{"component_id": "COMPONENT_RENDER", "kind": "source"}], "declared_boundaries": ["review"], "contract_change": False},
        "git_facts": {"source_tool": "git_facts_collector", "source_run_id": "RUN_GIT_RENDER", "working_tree_clean": False, "changed_component_ids": ["COMPONENT_RENDER"]},
        "evidence": {"source_tool": "evidence_package_builder", "source_run_id": "RUN_EVIDENCE_RENDER", "content_hash": "a" * 64, "lineage_complete": True, "observed_evidence_refs": ["EV_RENDER"], "candidate_evidence_refs": [], "missing_evidence_ids": [], "unknown_ids": []},
        "required_checks": [{"check_id": "CHECK_RENDER", "check_type": "test", "status": "passed", "source_tool": "test_result_parser", "evidence_refs": ["EV_RENDER"]}],
    }
    built = subprocess.run([sys.executable, "-m", "local_developer_worker.cli", "review", "build"], input=json.dumps(build_payload), text=True, capture_output=True, cwd=root, env=environment, check=False)
    package = json.loads(built.stdout)["data"]

    completed = subprocess.run([sys.executable, "-m", "local_developer_worker.cli", "review", "render"], input=json.dumps({"contract_version": "1.0.0", "format": "markdown", "review_package": package}), text=True, capture_output=True, cwd=root, env=environment, check=False)

    assert completed.returncode == 0
    output = json.loads(completed.stdout)
    assert output["tool"] == "review_package_renderer"
    assert output["data"]["format"] == "markdown"
    assert output["data"]["authority"]["model_invoked"] is False
    assert "# LDW Review Package" in output["data"]["artifact"]


def test_review_render_cli_emits_self_contained_html():
    root = Path(__file__).parents[2]
    environment = {**os.environ, "PYTHONPATH": str(root / "src"), "LDW_TELEMETRY_DISABLED": "1"}
    build_payload = {
        "contract_version": "1.0.0", "objective": "Render <unsafe> HTML safely.",
        "scope": {"scope_id": "SCOPE_HTML", "change_size": "local", "changed_components": [{"component_id": "COMPONENT_HTML", "kind": "source"}], "declared_boundaries": ["review"], "contract_change": False},
        "git_facts": {"source_tool": "git_facts_collector", "source_run_id": "RUN_GIT_HTML", "working_tree_clean": False, "changed_component_ids": ["COMPONENT_HTML"]},
        "evidence": {"source_tool": "evidence_package_builder", "source_run_id": "RUN_EVIDENCE_HTML", "content_hash": "a" * 64, "lineage_complete": True, "observed_evidence_refs": ["EV_HTML"], "candidate_evidence_refs": [], "missing_evidence_ids": [], "unknown_ids": []},
        "required_checks": [{"check_id": "CHECK_HTML", "check_type": "test", "status": "passed", "source_tool": "test_result_parser", "evidence_refs": ["EV_HTML"]}],
    }
    built = subprocess.run([sys.executable, "-m", "local_developer_worker.cli", "review", "build"], input=json.dumps(build_payload), text=True, capture_output=True, cwd=root, env=environment, check=False)
    package = json.loads(built.stdout)["data"]

    completed = subprocess.run([sys.executable, "-m", "local_developer_worker.cli", "review", "render"], input=json.dumps({"contract_version": "1.0.0", "format": "html", "review_package": package}), text=True, capture_output=True, cwd=root, env=environment, check=False)

    assert completed.returncode == 0
    output = json.loads(completed.stdout)
    assert output["data"]["format"] == "html"
    assert output["data"]["artifact"].startswith("<!doctype html>")
    assert "&lt;unsafe&gt;" in output["data"]["artifact"]
    assert "<script" not in output["data"]["artifact"].lower()
