from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

from .contracts import canonical_json, sha256
from .tools import parse_tests

ROOT = Path(__file__).parents[2]
REGISTRY_PATH = ROOT / "docs" / "stage_b_gate_registry.json"
BASE_COMMIT = "5a3d14654e55c51a60439d1478a227cf1fe5a77b"
EXPECTED_IDS = ["POLICY-01", "REF-01", *[f"GATE-{index:02d}" for index in range(1, 8)], "NR-01"]
VALID_INITIAL_STATUSES = {
    "not_started", "inputs_pending", "ready", "in_progress", "qa_pending", "judge_revise",
    "waiting_for_input", "waiting_for_owner", "complete", "failed", "blocked", "stopped",
}


def expected_phase_2_safety_matrix(baseline: str) -> str:
    expected = baseline.replace(
        '        (["log", "parse"], {"text": "INFO ready\\nopaque"}),\n',
        '        (["log", "parse"], {"text": "INFO ready\\nopaque"}),\n'
        '        (["log", "process"], {"text": "ERROR failed", "semantic": False}),\n'
        '        (["log", "cluster"], {"events": []}),\n',
    )
    expected = expected.replace(
        'ids=["doctor", "log-parse", "test-parse",',
        'ids=["doctor", "log-parse", "log-process", "log-cluster", "test-parse",',
    )
    expected = expected.replace(
        "    assert completed.returncode == 0\n",
        '    assert completed.returncode == (2 if args == ["log", "cluster"] else 0)\n',
    )
    expected = expected.replace(
        '{"task": "inspect", "repository_state": {}, "observed_log_events": [], "observed_test_results": [], "file_inventory": []},',
        '{"repository_root": str(ROOT), "task": "inspect", "repository_state": {}, "observed_log_events": [], "observed_test_results": [], "file_inventory": []},',
    )
    expected = expected.replace(
        '(["context", "pack"], {"files": [{"path": "src/a.py"}], "named_files": ["src/a.py"]}),',
        '(["context", "pack"], {"repository_root": str(ROOT), "files": [{"path": "src/a.py"}], "named_files": ["src/a.py"]}),',
    )
    expected = expected.replace(
        '            "LDW_TELEMETRY_DISABLED": "1",\n',
        '            "LDW_TELEMETRY_DISABLED": "1",\n'
        '            "LDW_SESSION_LOG_DIR": str(ROOT / ".repo_index" / "pytest_matrix_sessions"),\n',
    )
    expected = expected.replace(
        '            "PYTHONPATH": str(ROOT / "src"),\n',
        '            "PYTHONPATH": str(ROOT / "src"),\n'
        '            "LDW_POLICY_PATH": str(ROOT / "policy.toml"),\n',
    )
    expected = expected.replace(
        '        (["telemetry", "summary"], {}),\n',
        '        (["telemetry", "summary"], {}),\n'
        '        (["telemetry", "mark", "RUN-matrix", "unclear"], {}),\n',
    )
    expected = expected.replace(
        '"benchmark-run", "telemetry-summary", "portfolio-verify"',
        '"benchmark-run", "telemetry-summary", "telemetry-mark", "portfolio-verify"',
    )
    expected = expected.replace(
        '        (["portfolio", "status"], {}),\n',
        '        (["portfolio", "status"], {}),\n'
        '        (["ollama", "advise"], {"task": "Review one function"}),\n',
    )
    expected = expected.replace(
        '"portfolio-verify", "portfolio-status"]',
        '"portfolio-verify", "portfolio-status", "ollama-advise"]',
    )
    expected = expected.replace(
        '    assert completed.returncode == (2 if args == ["log", "cluster"] else 0)\n',
        '    assert completed.returncode == (2 if args in (["log", "cluster"], ["ollama", "advise"]) else 0)\n',
    )
    return expected


def load_phase_1_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    items = registry.get("items")
    if registry.get("schema_version") != "1.0.0" or not isinstance(items, list) or len(items) != 10:
        raise ValueError("Stage B Phase 1 registry must contain exactly 10 versioned items")
    if [item.get("id") for item in items if isinstance(item, dict)] != EXPECTED_IDS:
        raise ValueError("Stage B Phase 1 registry IDs or order are invalid")
    for item in items:
        required = {"id", "objective", "initial_status", "evidence_test_ids", "owner_action"}
        if not required <= set(item) or item["initial_status"] not in VALID_INITIAL_STATUSES:
            raise ValueError(f"invalid Phase 1 item: {item.get('id')}")
        nodes = item["evidence_test_ids"]
        if not isinstance(nodes, list) or not nodes or len(nodes) != len(set(nodes)):
            raise ValueError(f"invalid Phase 1 evidence: {item['id']}")
        for node in nodes:
            if not isinstance(node, str) or not re.fullmatch(r"tests/[^:]+::test_\S+", node):
                raise ValueError(f"invalid Phase 1 test node: {item['id']}")
            test_path = Path(node.split("::", 1)[0])
            if test_path.is_absolute() or ".." in test_path.parts:
                raise ValueError(f"unsafe Phase 1 test path: {item['id']}")
    if items[0]["id"] != "POLICY-01" or items[0]["initial_status"] != "ready":
        raise ValueError("POLICY-01 must start ready")
    return registry


def _run_test(node_id: str, timeout: int = 120) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-rA", node_id],
            cwd=ROOT,
            env={**os.environ, "LDW_TELEMETRY_DISABLED": "1"},
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        text = completed.stdout + completed.stderr
        exit_code = completed.returncode
    except subprocess.TimeoutExpired:
        text = "timeout"
        exit_code = 124
    except OSError:
        text = "test runner unavailable"
        exit_code = None
    parsed = parse_tests(
        {
            "text": text,
            "exit_code": exit_code,
            "command_observed": True,
            "source": node_id,
        }
    )
    observed = sorted({row["test_id"] for row in parsed.get("data", {}).get("tests", [])})
    return {
        "test_id": node_id,
        "run_status": parsed.get("data", {}).get("run_status", "unknown"),
        "exit_code": exit_code,
        "observed_test_ids": observed,
        "observed_test_count": len(observed),
        "evidence_hash": sha256(canonical_json(observed)),
    }


def _reconciliation() -> dict[str, Any]:
    reference = json.loads((ROOT / "fixtures" / "stage_b" / "reference_events.json").read_text())
    policy = tomllib.loads((ROOT / "policy.toml").read_text())
    relative = "tests/integration/test_stage_a_safety_matrix.py"
    baseline = subprocess.run(
        ["git", "show", f"{BASE_COMMIT}:{relative}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    current = (ROOT / relative).read_text()
    expected_matrix = expected_phase_2_safety_matrix(baseline.stdout.decode()) if baseline.returncode == 0 else None
    return {
        "registry_ids_exact": [item["id"] for item in load_phase_1_registry()["items"]] == EXPECTED_IDS,
        "reference_event_count": len(reference["events"]),
        "reference_minimum_met": len(reference["events"]) >= 30,
        "semantic_enabled": policy.get("semantic", {}).get("enabled"),
        "stage_a_safety_matrix_matches_authorized_phase_2_delta": expected_matrix is not None and current == expected_matrix,
        "semantic_group_schema_present": (ROOT / "schemas" / "semantic_group.schema.json").is_file(),
    }


def run_phase_1_portfolio(*, timeout: int = 120) -> dict[str, Any]:
    registry = load_phase_1_registry()
    items = []
    checks_observed = 0
    missing_checks = []
    for definition in registry["items"]:
        evidence = [_run_test(node, timeout) for node in definition["evidence_test_ids"]]
        checks_observed += sum(row["observed_test_count"] for row in evidence)
        failed = [row["test_id"] for row in evidence if row["run_status"] != "passed" or not row["observed_test_ids"]]
        missing_checks.extend(failed)
        items.append(
            {
                "id": definition["id"],
                "status": "complete" if not failed else "judge_revise",
                "evidence": evidence,
                "owner_action": definition["owner_action"],
            }
        )
    completed = [item["id"] for item in items if item["status"] == "complete"]
    partial = [item["id"] for item in items if item["status"] == "judge_revise"]
    blocked = [item["id"] for item in items if item["status"] == "blocked"]
    reconciliation = _reconciliation()
    reconciliation_ok = (
        reconciliation["registry_ids_exact"]
        and reconciliation["reference_minimum_met"]
        and reconciliation["semantic_enabled"] is False
        and reconciliation["stage_a_safety_matrix_matches_authorized_phase_2_delta"]
        and reconciliation["semantic_group_schema_present"]
    )
    acceptance = "phase_1_complete" if len(completed) == 10 and reconciliation_ok else "phase_1_partial"
    findings = [{"id": item["id"], "status": item["status"]} for item in items if item["status"] != "complete"]
    if not reconciliation_ok:
        findings.append({"id": "reconciliation", "status": "judge_revise"})
    next_item = next((item["id"] for item in items if item["status"] != "complete"), None)
    return {
        "goal": "Stage B regression gate (7 properties + needs_review rule + POLICY-01)",
        "execution_status": "success" if acceptance == "phase_1_complete" else "partial",
        "portfolio_size": len(items),
        "items": items,
        "completed": completed,
        "partial": partial,
        "blocked": blocked,
        "material_findings": findings,
        "reconciliation_results": reconciliation,
        "checks_observed": checks_observed,
        "missing_checks": missing_checks,
        "next_resumable_action": {
            "item_id": next_item,
            "command": "PYTHONPATH=src python scripts/run_stage_b_portfolio.py",
        } if next_item else None,
        "portfolio_acceptance": acceptance,
    }
