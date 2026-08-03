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
REGISTRY_PATH = ROOT / "docs" / "stage_b_phase_2_registry.json"
EXPECTED_IDS = [f"PB2-{index:02d}" for index in range(1, 9)]


def load_phase_2_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    items = registry.get("items")
    if registry.get("schema_version") != "1.0.0" or not isinstance(items, list) or len(items) != 8:
        raise ValueError("Stage B Phase 2 registry must contain exactly 8 versioned items")
    if [item.get("id") for item in items if isinstance(item, dict)] != EXPECTED_IDS:
        raise ValueError("Stage B Phase 2 registry IDs or order are invalid")
    for item in items:
        if set(item) != {"id", "objective", "evidence_test_ids", "owner_action"}:
            raise ValueError(f"invalid Phase 2 item: {item.get('id')}")
        nodes = item["evidence_test_ids"]
        if not isinstance(nodes, list) or not nodes or len(nodes) != len(set(nodes)):
            raise ValueError(f"invalid Phase 2 evidence: {item['id']}")
        if any(not isinstance(node, str) or not re.fullmatch(r"tests/[^:]+::test_\S+", node) for node in nodes):
            raise ValueError(f"invalid Phase 2 test node: {item['id']}")
    return registry


def _run_test(node_id: str, timeout: int) -> dict[str, Any]:
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
        text, exit_code = "timeout", 124
    except OSError:
        text, exit_code = "test runner unavailable", None
    parsed = parse_tests({"text": text, "exit_code": exit_code, "command_observed": True, "source": node_id})
    observed = sorted({row["test_id"] for row in parsed.get("data", {}).get("tests", [])})
    return {
        "test_id": node_id,
        "run_status": parsed.get("data", {}).get("run_status", "unknown"),
        "observed_test_count": len(observed),
        "evidence_hash": sha256(canonical_json(observed)),
    }


def _run_regression_portfolios(timeout: int) -> dict[str, Any]:
    environment = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "LDW_TELEMETRY_DISABLED": "1",
        "LDW_PORTFOLIO_STATE": str(ROOT / ".repo_index" / "phase_2_stage_a_state.json"),
    }
    try:
        stage_a = subprocess.run(
            [sys.executable, "-m", "local_developer_worker.cli", "portfolio", "verify"],
            input="{}", cwd=ROOT, env=environment, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        phase_1 = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_stage_b_portfolio.py")],
            cwd=ROOT, env=environment, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        stage_a_data = json.loads(stage_a.stdout).get("data", {}).get("portfolio", {})
        phase_1_data = json.loads(phase_1.stdout)
    except (json.JSONDecodeError, OSError, subprocess.TimeoutExpired):
        return {"passed": False, "stage_a_completed": 0, "phase_1_completed": 0}
    stage_a_completed = len(stage_a_data.get("completed_items", []))
    phase_1_completed = len(phase_1_data.get("completed", []))
    return {
        "passed": (
            stage_a.returncode == 0 and stage_a_completed == 20 and not stage_a_data.get("partial_items")
            and phase_1.returncode == 0 and phase_1_data.get("portfolio_acceptance") == "phase_1_complete"
            and phase_1_completed == 10
        ),
        "stage_a_completed": stage_a_completed,
        "phase_1_completed": phase_1_completed,
    }


def _reconciliation() -> dict[str, Any]:
    from . import cli

    policy = tomllib.loads((ROOT / "policy.toml").read_text())
    gate_registry = json.loads((ROOT / "docs" / "gate_registry.json").read_text())
    live = json.loads((ROOT / "fixtures" / "stage_b" / "phase_2_live_run_evidence.json").read_text())
    return {
        "registry_ids_exact": [item["id"] for item in load_phase_2_registry()["items"]] == EXPECTED_IDS,
        "command_registered": ("log", "cluster") in cli.COMMANDS,
        "semantic_default_off": policy["semantic"]["enabled"] is False and policy["automatic"]["semantic_log_clustering"] is False,
        "code_artifact_disabled": policy["semantic"]["code_artifact"] == "disabled",
        "model_and_endpoint_configured": policy["semantic"]["model"] == "qwen3:4b" and policy["semantic"]["endpoint"] == "http://127.0.0.1:11435/api/generate",
        "governed_feature_registered": any(item.get("id") == "PB2-LOG-CLUSTERING" for item in gate_registry.get("governed_features", [])),
        "real_model_response_observed": live["model_response_observed"] is True and live["raw_response_stored"] is False,
        "rollback_documented": (ROOT / "docs" / "stage-b-phase-2-rollback.md").is_file(),
    }


def run_phase_2_portfolio(*, timeout: int = 180) -> dict[str, Any]:
    registry = load_phase_2_registry()
    regressions = _run_regression_portfolios(timeout)
    items, missing_checks = [], []
    checks_observed = regressions["stage_a_completed"] + regressions["phase_1_completed"]
    for definition in registry["items"]:
        evidence = [_run_test(node, timeout) for node in definition["evidence_test_ids"]]
        checks_observed += sum(row["observed_test_count"] for row in evidence)
        failed = [row["test_id"] for row in evidence if row["run_status"] != "passed" or not row["observed_test_count"]]
        if definition["id"] == "PB2-06" and not regressions["passed"]:
            failed.append("Stage A 20/20 and Phase 1 10/10")
        status = "complete" if not failed else "judge_revise"
        missing_checks.extend(failed)
        items.append({"id": definition["id"], "status": status, "evidence": evidence, "owner_action": definition["owner_action"]})
    completed = [item["id"] for item in items if item["status"] == "complete"]
    partial = [item["id"] for item in items if item["status"] != "complete"]
    reconciliation = _reconciliation()
    reconciliation_ok = all(reconciliation.values())
    acceptance = "phase_2_complete" if len(completed) == 8 and reconciliation_ok else "phase_2_partial"
    findings = [
        {"classification": "OBSERVED", "id": "PB2-07", "finding": "qwen3:4b responded on 127.0.0.1:11435; candidate failed deterministic accounting checks and fallback preserved 34 observed events."}
    ]
    if not reconciliation_ok:
        findings.append({"classification": "OBSERVED", "id": "reconciliation", "finding": "one or more reconciliation checks failed"})
    next_item = next((item["id"] for item in items if item["status"] != "complete"), None)
    return {
        "goal": "Stage B Phase 2 — production log-clustering command",
        "execution_status": "success" if acceptance == "phase_2_complete" else "partial",
        "portfolio_size": 8,
        "items": items,
        "completed": completed,
        "partial": partial,
        "waiting_for_owner": [],
        "blocked": [],
        "material_findings": findings,
        "reconciliation_results": {**reconciliation, "stage_a_completed": regressions["stage_a_completed"], "phase_1_completed": regressions["phase_1_completed"]},
        "checks_observed": checks_observed,
        "missing_checks": missing_checks,
        "next_resumable_action": {"item_id": next_item, "command": "PYTHONPATH=src python scripts/run_stage_b_phase_2_portfolio.py"} if next_item else None,
        "portfolio_acceptance": acceptance,
    }
