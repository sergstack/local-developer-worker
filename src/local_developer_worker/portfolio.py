from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

from .contracts import canonical_json, result, sha256, stable_hash
from .session_log import iter_events
from .telemetry import SAFE_FIELDS

ROOT = Path(__file__).parents[2]
DEFAULT_REGISTRY = ROOT / "docs" / "gate_registry.json"
STATE_ROOT = ROOT / ".repo_index"
DEFAULT_STATE = STATE_ROOT / "portfolio_state.json"
VALID_STATUSES = {"not_started", "in_progress", "waiting_for_input", "judge_revise", "complete", "blocked"}
ARTIFACT_KINDS = {"path", "python_constant_equals", "jsonl_records", "cli_command_registered", "pytest_node_exists", "document_contract", "toml_value", "terminology_audit", "tool_data_equals"}


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path or DEFAULT_REGISTRY)
    data = json.loads(source.read_text(encoding="utf-8"))
    items = data.get("items")
    if data.get("schema_version") != "1.0.0" or not isinstance(items, list) or len(items) != 20:
        raise ValueError("portfolio registry must contain exactly 20 versioned items")
    ids = [item.get("id") for item in items if isinstance(item, dict)]
    expected = [f"SA-{index:02d}" for index in range(1, 17)] + [f"AI-{index:02d}" for index in range(1, 5)]
    if ids != expected or len(set(ids)) != 20:
        raise ValueError("portfolio registry IDs or order are invalid")
    for index, item in enumerate(items, 1):
        required = {"id", "category", "status", "evidence_test_ids", "classification", "last_verified_commit", "title", "owner_action"}
        if not required <= set(item):
            raise ValueError(f"missing required portfolio fields: {item.get('id')}")
        category = "gate" if index <= 16 else "action_item"
        if item.get("category") != category or item.get("status") not in VALID_STATUSES:
            raise ValueError(f"invalid portfolio item: {item.get('id')}")
        expected_classification = "architectural" if index <= 15 else "advisory" if index == 16 else "action_item"
        if item.get("classification") != expected_classification:
            raise ValueError(f"invalid classification: {item.get('id')}")
        tests = item.get("evidence_test_ids")
        if not isinstance(tests, list) or not all(isinstance(node, str) and re.fullmatch(r"tests/[^:]+::test_\S+", node) for node in tests) or len(tests) != len(set(tests)) or (category == "gate" and not tests):
            raise ValueError(f"invalid evidence tests: {item.get('id')}")
        for node in tests:
            test_path = PurePosixPath(node.split("::", 1)[0])
            if test_path.is_absolute() or ".." in test_path.parts:
                raise ValueError(f"unsafe evidence test path: {item.get('id')}")
        commit = item.get("last_verified_commit")
        if commit is not None and (not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{7,40}", commit)):
            raise ValueError(f"invalid last_verified_commit: {item.get('id')}")
        artifacts = item.get("artifacts", [])
        if not isinstance(artifacts, list) or any(not isinstance(check, dict) or check.get("kind") not in ARTIFACT_KINDS or not isinstance(check.get("check_id"), str) for check in artifacts):
            raise ValueError(f"invalid artifact checks: {item.get('id')}")
        for check in artifacts:
            if check.get("path"):
                artifact_path = PurePosixPath(check["path"])
                if artifact_path.is_absolute() or ".." in artifact_path.parts:
                    raise ValueError(f"unsafe artifact path: {item.get('id')}")
            if check["kind"] == "tool_data_equals" and (
                not isinstance(check.get("args"), list)
                or not check["args"]
                or not all(isinstance(value, str) for value in check["args"])
                or not isinstance(check.get("key"), str)
            ):
                raise ValueError(f"invalid tool data check: {item.get('id')}")
        check_ids = [check["check_id"] for check in artifacts]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError(f"duplicate artifact checks: {item.get('id')}")
        if category == "gate" and (not isinstance(item.get("guarantee"), str) or not isinstance(item.get("enforcement"), str)):
            raise ValueError(f"invalid gate contract: {item.get('id')}")
        if category == "action_item" and (not isinstance(item.get("source"), str) or "artifacts" not in item):
            raise ValueError(f"invalid action contract: {item.get('id')}")
    ai02 = items[17]
    options = ai02.get("decision_options", [])
    if ai02.get("forced_status") != "waiting_for_input" or [row.get("id") for row in options] != ["a", "b", "c"]:
        raise ValueError("AI-02 must remain waiting_for_input with options a, b and c")
    decision = ai02.get("decision")
    if decision is not None:
        chosen_option = decision.get("chosen_option") if isinstance(decision, dict) else None
        if chosen_option not in {"a", "c"} or not ai02.get("artifacts"):
            raise ValueError("AI-02 decision must choose an allowed option and provide artifact evidence")
    if next(row for row in options if row["id"] == "b").get("rejected") is not True:
        raise ValueError("AI-02 option b must remain rejected")
    return data


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_release_gates(registry: dict[str, Any]) -> str:
    gates = [item for item in registry["items"] if item["category"] == "gate"]
    actions = [item for item in registry["items"] if item["category"] == "action_item"]
    lines = [
        "# Release gates",
        "",
        "This file is generated from `docs/gate_registry.json`. Do not edit it by hand.",
        "Run `python scripts/generate_release_gates.py --check` to detect drift.",
        "",
        "`architectural` means the worker enforces the guarantee when the command is invoked;",
        "`advisory` means invocation itself is governed by the operating agreement.",
        "",
        "| ID | Public guarantee | Exact evidence test IDs | Enforcement mechanism | Classification |",
        "|---|---|---|---|---|",
    ]
    for item in gates:
        tests = "<br>".join(f"`{node}`" for node in item["evidence_test_ids"])
        lines.append(
            f"| {item['id']} | {_cell(item['guarantee'])} | {tests} | {_cell(item['enforcement'])} | {item['classification']} |"
        )
    lines.extend(
        [
            "",
            "The economic benchmark is informational only. Context-reduction figures are not a Stage A promotion gate and cannot be used as an acceptance blocker.",
            "",
            "## Stage A to B action items",
            "",
            "| ID | Action | Source | Initial status | Owner action |",
            "|---|---|---|---|---|",
        ]
    )
    for item in actions:
        lines.append(
            f"| {item['id']} | {_cell(item['title'])} | {_cell(item['source'])} | {item['status']} | {_cell(item['owner_action'])} |"
        )
    ai02 = next(item for item in actions if item["id"] == "AI-02")
    chosen_option = ai02.get("decision", {}).get("chosen_option")
    lines.extend(
        [
            "",
            "## AI-02 decision table",
            "",
            f"Selected option: `{chosen_option}`." if chosen_option else "No option is selected or implemented by this registry.",
            "",
            "| Option | Posture | Benefit | Tradeoff |",
            "|---|---|---|---|",
        ]
    )
    for option in ai02["decision_options"]:
        lines.append(
            f"| {option['id']} | {_cell(option['option'])} | {_cell(option['benefit'])} | {_cell(option['tradeoff'])} |"
        )
    wave2 = registry.get("wave_2_acceptance")
    if wave2:
        lines.extend(
            [
                "",
                "## Wave 2 — Context and Evidence Layer",
                "",
                f"Status: `{wave2['status']}`.",
                f"Overall state: `{wave2['overall_state']}`.",
                f"Global activation: `{wave2['global_activation']}`.",
                "",
                "| Service | Implemented | Accepted |",
                "|---|---|---|",
            ]
        )
        for service, state in wave2["services"].items():
            lines.append(f"| {service} | {str(state['implemented']).lower()} | {state['accepted']} |")
        acceptance = wave2["acceptance"]
        lines.extend(
            [
                "",
                "| Acceptance requirement | Value |",
                "|---|---|",
            ]
        )
        for key, value in acceptance.items():
            rendered_value = str(value).lower() if isinstance(value, bool) else str(value)
            lines.append(f"| {key} | {rendered_value} |")
        lines.extend(
            [
                "",
                "Exact evidence tests:",
                "",
                *[f"- `{node}`" for node in wave2["evidence_test_ids"]],
                "",
                "Forbidden:",
                "",
                *[f"- {item}" for item in wave2["forbidden"]],
            ]
        )
    posture = registry.get("stage_b_model_posture")
    if posture:
        lines.extend([
            "",
            "## Stage B model posture",
            "",
            f"Status: `{posture['status']}`.",
            "",
            "| Posture | Value | Classification |",
            "|---|---|---|",
        ])
        for key in ("recommended_quality_model", "configured_global_model", "actually_invoked_model", "activated_supervised_model", "fast_challenger", "formal_winner", "economic_winner"):
            item = posture[key]
            lines.append(f"| {key} | {item['value']} | {item['classification']} |")
        decision = posture["owner_decision"]
        supervised = posture["supervised_explicit_activation"]
        automatic = posture["automatic_routing"]
        lines.extend([
            "",
            f"Selected owner option: `{decision['selected_option']}`.",
            f"Recommendation: `{decision['recommendation']}`.",
            f"Supervised explicit activation active: `{str(supervised['active']).lower()}`.",
            "Supervised explicit blockers: " + (", ".join(f"`{item}`" for item in supervised["blockers"]) or "none") + ".",
            f"Automatic routing allowed: `{str(automatic['allowed']).lower()}`.",
            f"Automatic routing enabled: `{str(automatic['enabled']).lower()}`.",
        ])
    return "\n".join(lines) + "\n"


def _pytest_environment() -> dict[str, str]:
    environment = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "LDW_TELEMETRY_DISABLED": "1",
        "LDW_PORTFOLIO_STATE": str(ROOT / ".repo_index" / "pytest_portfolio_state.json"),
    }
    return environment


def _run_pytest(node_id: str, *, collect_only: bool, timeout: int) -> dict[str, Any]:
    command = [sys.executable, "-m", "pytest"]
    if collect_only:
        command.extend(["--collect-only", "-q", node_id])
    else:
        command.extend(["-q", node_id])
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=_pytest_environment(),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "return_code": completed.returncode,
            "stdout_sha256": sha256(completed.stdout),
            "stderr_sha256": sha256(completed.stderr),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "return_code": None,
            "timeout": True,
            "stdout_sha256": sha256(exc.stdout or b""),
            "stderr_sha256": sha256(exc.stderr or b""),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        }
    except OSError:
        return {"return_code": None, "execution_error": True, "elapsed_ms": 0}


def _collect_all_nodes(timeout: int) -> set[str]:
    try:
        collection = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            cwd=ROOT,
            env=_pytest_environment(),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if collection.returncode != 0:
        return set()
    return {line.strip() for line in collection.stdout.splitlines() if line.startswith("tests/") and "::" in line}


def _head_commit() -> str | None:
    completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else None


def _workspace_fingerprint(registry: dict[str, Any]) -> str:
    relative_paths = {
        "SPEC.md",
        "plan.md",
        "tasks.md",
        "README.md",
        "policy.toml",
        "docs/gate_registry.json",
        "docs/release-gates.md",
        "docs/authority-boundary.md",
        "schemas/portfolio_item.schema.json",
        "schemas/telemetry_event.schema.json",
        "scripts/generate_release_gates.py",
        "scripts/validate_schemas.py",
        "src/local_developer_worker/cli.py",
        "src/local_developer_worker/contracts.py",
        "src/local_developer_worker/portfolio.py",
        "src/local_developer_worker/session_log.py",
        "src/local_developer_worker/telemetry.py",
        "src/local_developer_worker/tools.py",
    }
    for item in registry["items"]:
        relative_paths.update(node_id.split("::", 1)[0] for node_id in item["evidence_test_ids"])
        relative_paths.update(
            check["path"]
            for check in item.get("artifacts", [])
            if check.get("path") and not check["path"].startswith(".repo_index/")
        )
    records = []
    for relative in sorted(relative_paths):
        path = ROOT / relative
        if path.is_file() and not path.is_symlink():
            records.append({"path": relative, "sha256": sha256(path.read_bytes())})
        else:
            records.append({"path": relative, "missing": True})
    return stable_hash(records)


def _state_path() -> Path:
    path = Path(os.environ.get("LDW_PORTFOLIO_STATE") or DEFAULT_STATE).resolve(strict=False)
    allowed_root = STATE_ROOT.resolve(strict=False)
    try:
        path.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError("portfolio state must stay under .repo_index") from exc
    return path


def _read_state() -> dict[str, Any] | None:
    try:
        path = _state_path()
    except ValueError:
        return None
    if not path.is_file() or path.is_symlink():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_state(state: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise OSError("portfolio state cannot be a symlink")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(canonical_json(state) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _python_constant(path: Path, symbol: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(isinstance(target, ast.Name) and target.id == symbol for target in statement.targets):
            return ast.literal_eval(statement.value)
    raise ValueError(f"constant not found: {symbol}")


def _artifact_result(check: dict[str, Any], collected_nodes: set[str], commit: str | None) -> dict[str, Any]:
    kind = check["kind"]
    evidence: dict[str, Any] = {"check_id": check["check_id"], "kind": kind, "status": "failed", "observed_commit": commit}
    try:
        if kind == "path":
            path = ROOT / check["path"]
            passed = path.is_file()
            detail = {"exists": passed, "sha256": sha256(path.read_bytes()) if passed else None}
        elif kind == "python_constant_equals":
            value = _python_constant(ROOT / check["path"], check["symbol"])
            observed = sorted(value) if isinstance(value, (set, tuple, list)) else value
            passed = observed == check["expected"]
            detail = {"matches": passed, "observed_hash": stable_hash(observed)}
        elif kind == "jsonl_records":
            events, invalid = iter_events(ROOT / check["path"])
            exact = set(check.get("exact_fields", []))
            passed = len(events) >= check["minimum"] and invalid == 0 and all(set(event) == exact for event in events)
            detail = {
                "observed_count": len(events),
                "minimum": check["minimum"],
                "invalid_records": invalid,
                "journal_hash": stable_hash(events),
            }
        elif kind == "cli_command_registered":
            from . import cli

            args = tuple(check["args"])
            passed = args in cli.COMMANDS
            detail = {"registered": passed, "command": " ".join(args)}
        elif kind == "pytest_node_exists":
            passed = check["node_id"] in collected_nodes
            detail = {"collected": passed, "node_id": check["node_id"]}
        elif kind == "document_contract":
            path = ROOT / check["path"]
            text = path.read_text(encoding="utf-8")
            missing_sections = [section for section in check.get("required_sections", []) if f"## {section}" not in text]
            missing_phrases = [phrase for phrase in check.get("required_phrases", []) if phrase not in text]
            forbidden = [pattern for pattern in check.get("forbidden_patterns", []) if re.search(pattern, text, re.I)]
            passed = not missing_sections and not missing_phrases and not forbidden
            detail = {
                "sha256": sha256(text),
                "missing_sections": missing_sections,
                "missing_phrases": missing_phrases,
                "forbidden_matches": forbidden,
            }
        elif kind == "toml_value":
            value = tomllib.loads((ROOT / check["path"]).read_text(encoding="utf-8"))[check["table"]][check["key"]]
            passed = value == check["expected"]
            detail = {"matches": passed, "value": value}
        elif kind == "terminology_audit":
            text = (ROOT / check["path"]).read_text(encoding="utf-8")
            missing = [phrase for phrase in check.get("required_phrases", []) if phrase not in text]
            forbidden = [pattern for pattern in check.get("forbidden_patterns", []) if re.search(pattern, text, re.I)]
            passed = not missing and not forbidden
            detail = {"sha256": sha256(text), "missing_phrases": missing, "forbidden_matches": forbidden}
        elif kind == "tool_data_equals":
            from . import cli

            output = cli.COMMANDS[tuple(check["args"])]({})
            observed = output.get("data", {}).get(check["key"])
            passed = output.get("status") == "success" and observed == check["expected"]
            detail = {"matches": passed, "observed_hash": stable_hash(observed)}
        else:
            raise ValueError(f"unsupported artifact kind: {kind}")
        evidence["status"] = "passed" if passed else "failed"
        evidence["detail"] = detail
    except (ImportError, KeyError, OSError, TypeError, ValueError, SyntaxError) as exc:
        evidence["detail"] = {"error": type(exc).__name__}
    return evidence


def _initial_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "category": item["category"],
        "classification": item["classification"],
        "status": "waiting_for_input" if item["id"] == "AI-02" and "decision" not in item else "not_started",
        "evidence": [],
        "last_verified_commit": None,
        "workspace_fingerprint": None,
        "owner_action": item["owner_action"],
    }


def _portfolio_view(items: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [item["id"] for item in items if item["status"] == "complete"]
    partial = [item["id"] for item in items if item["status"] in {"in_progress", "judge_revise"}]
    blockers = [
        {"id": item["id"], "status": item["status"], "owner_action": item["owner_action"]}
        for item in items
        if item["status"] in {"waiting_for_input", "judge_revise", "blocked"}
    ]
    next_item = next((item for item in items if item["status"] not in {"complete", "waiting_for_input"}), None)
    if next_item is None:
        next_item = next((item for item in items if item["status"] == "waiting_for_input"), None)
    return {
        "item_count": len(items),
        "items": items,
        "completed_items": completed,
        "partial_items": partial,
        "blockers": blockers,
        "next_resumable_command": f"ldw portfolio verify --only {next_item['id']}" if next_item else None,
    }


def portfolio_verify(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    try:
        registry = load_registry()
        requested = payload.get("only")
        selected = {requested} if isinstance(requested, str) else set(requested or [item["id"] for item in registry["items"]])
        known = {item["id"] for item in registry["items"]}
        if not selected or not selected <= known:
            raise ValueError("only contains an unknown portfolio ID")
        timeout = min(max(int(payload.get("timeout_seconds", 60)), 1), 300)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return result("portfolio_verify", "registry", raw, {}, status="invalid_input", errors=[{"code": "invalid_portfolio", "detail": str(exc)}])

    commit = _head_commit()
    fingerprint = _workspace_fingerprint(registry)
    existing = _read_state()
    existing_items = {item["id"]: item for item in (existing or {}).get("items", []) if isinstance(item, dict) and item.get("id")}
    current_items = []
    for definition in registry["items"]:
        prior = existing_items.get(definition["id"])
        if prior and prior.get("workspace_fingerprint") == fingerprint and prior.get("last_verified_commit") == commit:
            current_items.append(prior)
        else:
            current_items.append(_initial_item(definition))
    by_id = {item["id"]: item for item in current_items}

    needs_collection = any(item["id"] in selected and (item["category"] == "gate" or any(check["kind"] == "pytest_node_exists" for check in item.get("artifacts", []))) for item in registry["items"])
    collected_nodes: set[str] = set()
    if needs_collection:
        collected_nodes = _collect_all_nodes(timeout)

    generated = render_release_gates(registry)
    release_path = ROOT / "docs" / "release-gates.md"
    document_in_sync = release_path.is_file() and release_path.read_text(encoding="utf-8") == generated
    findings = []
    if not document_in_sync:
        findings.append({"code": "generated_document_drift", "path": "docs/release-gates.md"})

    for definition in registry["items"]:
        if definition["id"] not in selected:
            continue
        item = _initial_item(definition)
        item["last_verified_commit"] = commit
        item["workspace_fingerprint"] = fingerprint
        if definition["category"] == "gate":
            evidence = []
            for node_id in definition["evidence_test_ids"]:
                collect = _run_pytest(node_id, collect_only=True, timeout=timeout)
                execute = _run_pytest(node_id, collect_only=False, timeout=timeout) if collect.get("return_code") == 0 and node_id in collected_nodes else None
                evidence.append(
                    {
                        "test_id": node_id,
                        "collected": collect.get("return_code") == 0 and node_id in collected_nodes,
                        "passed": bool(execute and execute.get("return_code") == 0),
                        "collect": collect,
                        "execute": execute,
                    }
                )
            item["evidence"] = evidence
            passed = all(row["collected"] and row["passed"] for row in evidence)
            enforcement = definition["enforcement"].lower()
            if definition["classification"] == "advisory":
                classification_valid = (
                    definition["id"] == "SA-16"
                    and "no hook" in enforcement
                    and "shell wrapper" in enforcement
                    and "interception" in enforcement
                    and any("authority_boundary" in node_id for node_id in definition["evidence_test_ids"])
                )
            else:
                classification_valid = definition["id"] != "SA-16" and "prompt and operating agreement only" not in enforcement
            item["status"] = "complete" if passed and classification_valid and document_in_sync else "judge_revise"
            if item["status"] != "complete":
                findings.append({"code": "gate_reconciliation_failed", "id": definition["id"]})
        elif definition["id"] == "AI-02" and "decision" not in definition:
            item["status"] = "waiting_for_input"
            item["evidence"] = [{"check_id": "AI-02-options", "status": "passed", "option_ids": ["a", "b", "c"], "observed_commit": commit}]
        else:
            evidence = [_artifact_result(check, collected_nodes, commit) for check in definition.get("artifacts", [])]
            item["evidence"] = evidence
            if evidence and all(row["status"] == "passed" for row in evidence):
                item["status"] = "complete"
            elif any(row.get("detail", {}).get("forbidden_matches") for row in evidence):
                item["status"] = "judge_revise"
            else:
                item["status"] = "in_progress"
        by_id[item["id"]] = item

    ordered = [by_id[item["id"]] for item in registry["items"]]
    view = _portfolio_view(ordered)
    view.update(
        {
            "verified_commit": commit,
            "workspace_fingerprint": fingerprint,
            "selected_items": [item["id"] for item in registry["items"] if item["id"] in selected],
            "reconciliation_findings": findings,
            "generated_document_in_sync": document_in_sync,
        }
    )
    state = {"schema_version": "1.0.0", "last_verified_commit": commit, "workspace_fingerprint": fingerprint, "items": ordered}
    try:
        _write_state(state)
    except (OSError, ValueError):
        return result("portfolio_verify", "registry", raw, {"portfolio": view}, status="partial", warnings=[{"code": "portfolio_state_not_saved"}])
    has_defect = any(item["status"] in {"not_started", "in_progress", "judge_revise", "blocked"} for item in ordered)
    return result("portfolio_verify", "registry", raw, {"portfolio": view}, status="partial" if has_defect else "success")


def portfolio_status(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    try:
        registry = load_registry()
        commit = _head_commit()
        fingerprint = _workspace_fingerprint(registry)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return result("portfolio_status", "registry", raw, {}, status="invalid_input", errors=[{"code": "invalid_portfolio", "detail": str(exc)}])
    state = _read_state()
    state_items = {item["id"]: item for item in (state or {}).get("items", []) if isinstance(item, dict) and item.get("id")}
    items = []
    for definition in registry["items"]:
        item = state_items.get(definition["id"], _initial_item(definition))
        if item.get("status") == "complete" and (item.get("last_verified_commit") != commit or item.get("workspace_fingerprint") != fingerprint):
            item = {**item, "status": "judge_revise", "owner_action": "Run a fresh portfolio verification for the current workspace."}
        if definition["id"] == "AI-02" and "decision" not in definition:
            item = {**item, "status": "waiting_for_input"}
        items.append(item)
    view = _portfolio_view(items)
    view.update({"verified_commit": commit, "workspace_fingerprint": fingerprint, "state_found": state is not None})
    has_defect = any(item["status"] in {"not_started", "in_progress", "judge_revise", "blocked"} for item in items)
    return result("portfolio_status", "registry", raw, {"portfolio": view}, status="partial" if has_defect else "success")
