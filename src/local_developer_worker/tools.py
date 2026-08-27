from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from .contracts import SourceReference, canonical_json, manifest, result, sha256, stable_hash

SECRET_NAME = re.compile(
    r"(^|/)(?:\.env(?:\..*)?|\.repo_index(?:/.*)?|.*(?:secret|credential|password|token|private[_-]?key|auth[_-]?store|provider[_-]?raw[_-]?response).*)(?:$|/)",
    re.I,
)
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
PY_LOCATION = re.compile(r'File "(?P<file>[^\"]+)", line (?P<line>\d+)')
PYTEST_FAILURE = re.compile(r"^FAILED\s+(?P<test>\S+)")
PYTEST_PASS = re.compile(r"^PASSED\s+(?P<test>\S+)")
PYTEST_OTHER = re.compile(r"^(?P<state>SKIPPED|XFAIL|XPASS|ERROR)\s+(?P<test>\S+)")
DOCKER_ERROR = re.compile(r"(?:ERROR|error|failed|Exited \(\d+\))", re.I)
TIMEOUT_LINE = re.compile(r"^(?!PASSED\s|FAILED\s|SKIPPED\s|XFAIL\s|XPASS\s|ERROR\s).*\b(?:timeout|timed out)\b", re.I | re.M)
TEST_STATUS_REMINDER = "Test status must be established via ldw test parse. Reading pytest or other test-runner output directly to determine pass/fail is not permitted."
WAVE2_CONTRACT_VERSION = "2.0.0"
DEFAULT_MAX_EXPANSION_DEPTH = 2
WAVE2_ORIGINS = {"observed", "deterministic-derived", "model-derived-candidate", "user-provided", "unknown"}
WAVE2_EXCLUSION_REASONS = {
    "outside_repository_root", "sensitive_path", "ignored_by_policy", "binary",
    "generated_not_required", "over_context_limit", "not_selected", "redundant_content", "unsupported",
}


def _is_sensitive_path(path: str) -> bool:
    return PurePosixPath(path).name != "secret_scan.py" and bool(SECRET_NAME.search(path))


def _safe_root(value: str) -> Path:
    root = Path(value).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("repository_root must be a directory")
    return root


def _inside(root: Path, value: Path) -> bool:
    try:
        value.resolve(strict=False).relative_to(root)
        return True
    except ValueError:
        return False


def parse_log(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("text")
    if not isinstance(text, str):
        return result("structured_log_parser", "stdin", canonical_json(payload), {}, status="invalid_input", errors=[{"code": "text_required"}])
    source = str(payload.get("source", "stdin"))
    events: list[dict[str, Any]] = []
    lines = text.splitlines()
    for index, original in enumerate(lines, 1):
        clean = ANSI.sub("", original)
        state, level, component = "unknown_event", "unknown", "generic"
        if not clean:
            state, level = "part_of_event", "info"
        elif re.search(r"\b(error|exception|traceback|failed)\b", clean, re.I):
            state, level = "parsed", "error"
        elif re.search(r"\b(warn|warning)\b", clean, re.I):
            state, level = "parsed", "warning"
        elif re.search(r"\b(info|passed|success)\b", clean, re.I):
            state, level = "parsed", "info"
        if "pytest" in clean.lower() or "test session starts" in clean.lower():
            component = "pytest"
        elif "docker" in clean.lower():
            component = "docker_compose"
        location = PY_LOCATION.search(clean)
        event = {
            "event_id": f"EV-{index:06d}", "level": level, "component": component,
            "message": clean, "exception_type": "AssertionError" if "AssertionError" in clean else None,
            "source_file": location.group("file") if location else None,
            "source_line": int(location.group("line")) if location else None,
            "raw_line_start": index, "raw_line_end": index, "raw_hash": sha256(original), "parse_status": state,
        }
        events.append(event)
    states = {state: sum(1 for event in events if event["parse_status"] == state) for state in ["parsed", "part_of_event", "unknown_event", "unsupported_format", "parse_failed"]}
    status = "success" if not states["unknown_event"] else "partial"
    return result("structured_log_parser", source, text, {"events": events, "line_accounting": {"input_lines": len(lines), **states}}, status=status, warnings=[{"code": "unknown_lines", "count": states["unknown_event"]}] if states["unknown_event"] else [])


def parse_tests(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("text", "")
    if not isinstance(text, str):
        return result("test_result_parser", "stdin", canonical_json(payload), {}, status="invalid_input", errors=[{"code": "text_must_be_string"}])
    exit_code = payload.get("exit_code")
    observed_command = bool(payload.get("command_observed", False))
    tests: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        match = PYTEST_PASS.match(line)
        outcome = "passed"
        if not match:
            match, outcome = PYTEST_FAILURE.match(line), "failed"
        if not match:
            match = PYTEST_OTHER.match(line)
            if match:
                outcome = {"SKIPPED": "skipped", "XFAIL": "xfailed", "XPASS": "xpassed", "ERROR": "error"}[match.group("state")]
        if match:
            tests.append({"test_id": match.group("test"), "status": outcome, "evidence": SourceReference("stdin", sha256(line), line_no, line_no).__dict__})
    lowered = text.lower()
    if not observed_command:
        run_status = "not_run"
    elif exit_code == 124 or TIMEOUT_LINE.search(text):
        run_status = "timeout"
    elif exit_code in (137, -9) or "killed" in lowered or "sigkill" in lowered:
        run_status = "incomplete"
    elif "no tests ran" in lowered or "not collected" in lowered:
        run_status = "not_collected"
    elif "error collecting" in lowered or "collection error" in lowered:
        run_status = "error"
    elif exit_code is None:
        run_status = "incomplete" if tests else "unknown"
    elif tests and exit_code == 0:
        run_status = "passed" if all(item["status"] == "passed" for item in tests) else "unknown"
    elif tests and exit_code != 0:
        run_status = "failed" if any(item["status"] == "failed" for item in tests) else "error"
    else:
        run_status = "unknown"
    status = "partial" if run_status in {"incomplete", "unknown", "not_run", "timeout"} else "success"
    return result("test_result_parser", str(payload.get("source", "stdin")), text, {"run_status": run_status, "exit_code": exit_code, "tests": tests, "command_observed": observed_command}, status=status)


def git_facts(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    try:
        root = _safe_root(str(payload["repository_root"]))
    except (KeyError, ValueError, FileNotFoundError) as exc:
        return result("git_facts_collector", "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_repository_root", "detail": str(exc)}])
    def git(*args: str) -> str:
        completed = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
        if completed.returncode:
            raise ValueError(completed.stderr.strip() or "not a git repository")
        return completed.stdout
    try:
        try:
            branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
            has_head = True
        except ValueError:
            branch = git("symbolic-ref", "--short", "HEAD").strip()
            has_head = False
        porcelain = git("status", "--porcelain=v1", "-z")
        changed, staged, unstaged, untracked = [], [], [], []
        for record in filter(None, porcelain.split("\0")):
            code, path = record[:2], record[3:]
            changed.append(path)
            if code == "??": untracked.append(path)
            if code[0] != " " and code != "??": staged.append(path)
            if code[1] != " " and code != "??": unstaged.append(path)
        numstat = git("diff", "--numstat", "HEAD") if has_head else git("diff", "--numstat", "--cached")
        additions = deletions = 0
        for line in filter(None, numstat.splitlines()):
            add, delete, _ = line.split("\t", 2)
            if add.isdigit(): additions += int(add)
            if delete.isdigit(): deletions += int(delete)
        data = {"current_branch": branch, "detached": branch == "HEAD", "changed_files": sorted(set(changed)), "staged_files": sorted(set(staged)), "unstaged_files": sorted(set(unstaged)), "untracked_files": sorted(set(untracked)), "additions": additions, "deletions": deletions, "working_tree_clean": not changed, "comparison_base": "HEAD" if has_head else None, "command_evidence": payload.get("command_evidence", [])}
        return result("git_facts_collector", str(root), raw, data)
    except ValueError as exc:
        return result("git_facts_collector", str(root), raw, {}, status="unsupported", errors=[{"code": "git_unavailable", "detail": str(exc)}])


def file_inventory(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    try:
        root = _safe_root(str(payload["repository_root"]))
    except (KeyError, ValueError, FileNotFoundError) as exc:
        return result("file_inventory", "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_repository_root", "detail": str(exc)}])
    max_bytes = int(payload.get("max_file_size", 5 * 1024 * 1024))
    records, warnings = [], []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if ".git/" in relative or relative == ".git": continue
        sensitive = _is_sensitive_path(relative)
        if path.is_symlink() and not _inside(root, path):
            records.append({"path": relative, "type": "symlink", "readable": False, "blocked": "symlink_escape", "potentially_sensitive": sensitive})
            continue
        try:
            stat = path.stat()
        except OSError:
            records.append({"path": relative, "type": "unknown", "readable": False, "blocked": "unreadable", "potentially_sensitive": sensitive})
            continue
        if path.is_dir(): continue
        binary = False
        sample = b""
        if not sensitive and stat.st_size <= max_bytes:
            try:
                sample = path.read_bytes()[:8192]
                binary = b"\0" in sample
            except OSError:
                pass
        if b"-----BEGIN " in sample and b"PRIVATE KEY-----" in sample or re.search(rb"(?:api[_-]?key|token|password)\s*[:=]", sample, re.I):
            sensitive = True
        blocked = "sensitive_path" if sensitive else ("size_limit" if stat.st_size > max_bytes else None)
        records.append({"path": relative, "type": "file", "size": stat.st_size, "extension": path.suffix.lower(), "binary": binary, "symlink": path.is_symlink(), "generated_candidate": relative.startswith(("build/", "dist/")) or relative.endswith((".generated.py", ".min.js")), "potentially_sensitive": sensitive, "ignored_by_policy": bool(blocked), "readable": not bool(blocked), "hash": None if blocked or binary else sha256(path.read_bytes())})
    return result("file_inventory", str(root), raw, {"files": records}, status="partial" if any(r.get("ignored_by_policy") or r.get("blocked") for r in records) else "success")


def _wave2_root(payload: dict[str, Any]) -> tuple[Path, bool]:
    value = payload.get("repository_root")
    if value is None:
        return Path.cwd().resolve(), False
    if not isinstance(value, str) or not value:
        raise ValueError("repository_root must be a non-empty string")
    return _safe_root(value), True


def _safe_relative_path(root: Path, value: Any) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or not value or "\\" in value:
        return None, "unsupported"
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
        return None, "outside_repository_root"
    normalized = relative.as_posix()
    candidate = root / normalized
    if not _inside(root, candidate):
        return None, "outside_repository_root"
    if candidate.is_symlink() and not _inside(root, candidate):
        return None, "outside_repository_root"
    return normalized, None


def _legacy_exclusion_reason(reason_code: str, *, duplicate: bool = False) -> str:
    if duplicate:
        return "duplicate_path"
    return {
        "sensitive_path": "sensitive_blocked",
        "over_context_limit": "context_budget",
        "not_selected": "no_deterministic_signal",
    }.get(reason_code, reason_code)


def _excluded_file(path: str, reason_code: str, policy_rule: str, *, duplicate: bool = False) -> dict[str, Any]:
    if reason_code not in WAVE2_EXCLUSION_REASONS:
        raise ValueError(f"unsupported exclusion reason: {reason_code}")
    return {
        "path": path,
        "included": False,
        "reason": _legacy_exclusion_reason(reason_code, duplicate=duplicate),
        "reason_code": reason_code,
        "policy_rule": policy_rule,
    }


def _selection_signals(payload: dict[str, Any]) -> tuple[dict[str, list[dict[str, str]]], set[str]]:
    signals: dict[str, list[dict[str, str]]] = {}

    def add(path: Any, reason: str, source: str, relevance: str) -> None:
        if isinstance(path, str) and path:
            signals.setdefault(path, []).append({
                "selection_reason": reason,
                "evidence_source": source,
                "relevance_status": relevance,
            })

    target_files = set(payload.get("target_files", [])) | set(payload.get("named_files", []))
    changed_files = set(payload.get("changed_files", []))
    failure_files = set(payload.get("failure_files", []))
    for failure in payload.get("observed_failures", []):
        if isinstance(failure, dict):
            candidate = failure.get("source_path") or failure.get("source_file") or failure.get("path")
            if isinstance(candidate, str):
                failure_files.add(candidate)
    related_tests = set(payload.get("related_tests", []))
    for path in sorted(target_files):
        add(path, "explicit_target", "target_files", "explicit")
    for path in sorted(changed_files):
        add(path, "changed_file", "changed_files", "candidate")
    for path in sorted(failure_files):
        add(path, "observed_failure_source", "observed_failures", "deterministic_dependency")
    for path in sorted(related_tests):
        add(path, "related_test", "related_tests", "deterministic_dependency")
    import_edges = payload.get("imports", payload.get("import_edges", {}))
    direct = target_files | changed_files | failure_files
    if isinstance(import_edges, dict):
        for origin, targets in sorted(import_edges.items()):
            if origin in direct and isinstance(targets, list):
                for target in targets:
                    add(target, "direct_import", f"imports:{origin}", "deterministic_dependency")
    return signals, direct


def _select_context(payload: dict[str, Any], root: Path, limit: int, forced_paths: set[str] | None = None) -> dict[str, Any]:
    files = payload.get("files", [])
    if not isinstance(files, list):
        raise TypeError("files_must_be_list")
    signals, direct = _selection_signals(payload)
    forced = forced_paths or set()
    for path in sorted(forced):
        signals.setdefault(path, []).insert(0, {
            "selection_reason": "bounded_expansion_request",
            "evidence_source": "requested_paths",
            "relevance_status": "explicit",
        })
    target_symbols = set(payload.get("target_symbols", []))
    candidates: dict[str, dict[str, Any]] = {}
    excluded: list[dict[str, Any]] = []
    seen: set[str] = set()
    eligible_input_bytes = 0
    for raw_item in files:
        item = raw_item if isinstance(raw_item, dict) else {"path": str(raw_item)}
        raw_path = item.get("path")
        path, path_issue = _safe_relative_path(root, raw_path)
        display_path = raw_path if isinstance(raw_path, str) and raw_path else "<invalid>"
        if path_issue:
            excluded.append(_excluded_file(display_path, path_issue, "repository_root_boundary"))
            continue
        assert path is not None
        if path in seen:
            excluded.append(_excluded_file(path, "not_selected", "duplicate_candidate", duplicate=True))
            continue
        seen.add(path)
        sensitive = bool(item.get("potentially_sensitive")) or _is_sensitive_path(path)
        if sensitive:
            excluded.append(_excluded_file(path, "sensitive_path", "sensitive_path_policy"))
            continue
        if item.get("ignored_by_policy"):
            excluded.append(_excluded_file(path, "ignored_by_policy", "inventory_policy"))
            continue
        if item.get("binary"):
            excluded.append(_excluded_file(path, "binary", "binary_content_policy"))
            continue
        size = item.get("size_bytes", item.get("size", 0))
        size = size if isinstance(size, int) and not isinstance(size, bool) and size >= 0 else 0
        eligible_input_bytes += size
        reasons = list(signals.get(path, []))
        symbols = item.get("symbols", [])
        matched_symbols = sorted(target_symbols & set(symbols if isinstance(symbols, list) else []))
        if matched_symbols:
            reasons.insert(0, {
                "selection_reason": "explicit_symbol",
                "evidence_source": "target_symbols",
                "relevance_status": "explicit",
            })
        if path.startswith("tests/") and path not in signals:
            test_relative = Path(path).relative_to("tests")
            source_relatives = {test_relative}
            if test_relative.name.startswith("test_"):
                source_relatives.add(test_relative.with_name(test_relative.name.removeprefix("test_")))
            related_sources = {Path("src", relative).as_posix() for relative in source_relatives}
            if related_sources & direct:
                reasons.append({
                    "selection_reason": "related_test",
                    "evidence_source": "pytest_path_convention",
                    "relevance_status": "deterministic_dependency",
                })
        explicit = any(reason["relevance_status"] == "explicit" for reason in reasons)
        if item.get("generated_candidate") and not explicit:
            excluded.append(_excluded_file(path, "generated_not_required", "generated_artifact_policy"))
            continue
        if not reasons:
            excluded.append(_excluded_file(path, "not_selected", "no_deterministic_signal"))
            continue
        primary = reasons[0]
        legacy_reasons = [
            {
                "explicit_target": "explicitly_named",
                "explicit_symbol": "explicitly_named",
                "observed_failure_source": "failure_source",
                "bounded_expansion_request": "explicitly_named",
            }.get(reason["selection_reason"], reason["selection_reason"])
            for reason in reasons
        ]
        candidates[path] = {
            "path": path,
            "included": True,
            "reasons": legacy_reasons,
            "selection_reason": primary["selection_reason"],
            "selection_reasons": reasons,
            "evidence_source": primary["evidence_source"],
            "relevance_status": primary["relevance_status"],
            "size_bytes": size,
            "symbols": matched_symbols,
            "content_hash": item.get("hash") if isinstance(item.get("hash"), str) and re.fullmatch(r"[0-9a-f]{64}", item["hash"]) else None,
        }
    for signaled_path in sorted(set(signals) - seen):
        path, path_issue = _safe_relative_path(root, signaled_path)
        if path_issue:
            excluded.append(_excluded_file(signaled_path, path_issue, "repository_root_boundary"))
        elif path is not None and _is_sensitive_path(path):
            excluded.append(_excluded_file(path, "sensitive_path", "sensitive_path_policy"))
        else:
            excluded.append(_excluded_file(path or signaled_path, "unsupported", "candidate_not_in_inventory"))
    def rank(item: dict[str, Any]) -> tuple[int, int, str]:
        return (
            {"explicit": 0, "deterministic_dependency": 1, "candidate": 2, "unknown": 3}[item["relevance_status"]],
            -len(item["selection_reasons"]),
            item["path"],
        )

    for content_hash in sorted({item["content_hash"] for item in candidates.values() if item["content_hash"]}):
        identical = sorted((item for item in candidates.values() if item["content_hash"] == content_hash), key=rank)
        if len(identical) < 2 or sum(item["relevance_status"] == "explicit" for item in identical) > 1:
            continue
        canonical = identical[0]
        for duplicate in identical[1:]:
            if duplicate["relevance_status"] == "explicit":
                continue
            del candidates[duplicate["path"]]
            excluded.append(_excluded_file(
                duplicate["path"], "redundant_content", f"identical_content_hash_to:{canonical['path']}"
            ))

    ranked = sorted(candidates.values(), key=rank)
    included = ranked[:limit]
    for item in ranked[limit:]:
        excluded.append(_excluded_file(item["path"], "over_context_limit", "max_context_files"))
    included_paths = {item["path"] for item in included}
    selected_bytes = sum(item["size_bytes"] for item in included)
    reduction = round((eligible_input_bytes - selected_bytes) / eligible_input_bytes, 4) if eligible_input_bytes else None
    safe_expandable = any(
        item["reason_code"] in {"not_selected", "generated_not_required", "over_context_limit"}
        for item in excluded
    )
    selection_status = "selected"
    if not included:
        selection_status = "unsupported"
    elif reduction is not None and reduction < 0.25:
        selection_status = "low_benefit_bypass"
    return {
        "included_files": included,
        "excluded_files": sorted(excluded, key=lambda item: (item["path"], item["reason_code"])),
        "included_paths": included_paths,
        "eligible_input_bytes": eligible_input_bytes,
        "selected_bytes": selected_bytes,
        "context_reduction": reduction,
        "selection_status": selection_status,
        "expansion_available": safe_expandable,
    }


def _python_slices(root: Path, included: list[dict[str, Any]], symbols: set[str]) -> list[dict[str, Any]]:
    """Return deterministic, AST-bounded slices; unsupported inputs retain whole-file fallback."""
    slices = []
    for item in included:
        path = item["path"]
        source_path = root / path
        if not symbols or source_path.suffix != ".py" or not source_path.is_file():
            continue
        try:
            source = source_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, UnicodeDecodeError, SyntaxError):
            slices.append({"path": path, "mode": "whole_file_fallback", "reason": "unsupported_python_syntax", "symbols": [], "ranges": []})
            continue
        lines = source.splitlines(keepends=True)
        imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        definitions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        constants = {
            target.id: node for node in tree.body if isinstance(node, ast.Assign)
            for target in node.targets if isinstance(target, ast.Name)
        }
        selected = [definitions[name] for name in sorted(symbols & definitions.keys())]
        referenced = {child.id for node in selected for child in ast.walk(node) if isinstance(child, ast.Name)}
        selected += [definitions[name] for name in sorted(referenced & definitions.keys()) if definitions[name] not in selected]
        referenced = {child.id for node in selected for child in ast.walk(node) if isinstance(child, ast.Name)}
        selected += [constants[name] for name in sorted(referenced & constants.keys()) if constants[name] not in selected]
        if not selected:
            continue
        ranges = [(node.lineno, node.end_lineno) for node in imports]
        ranges += [(min([node.lineno, *(decorator.lineno for decorator in getattr(node, "decorator_list", []))]), node.end_lineno) for node in selected]
        ranges = sorted(set(ranges))
        content = "".join("".join(lines[start - 1:end]) for start, end in ranges)
        slices.append({"path": path, "mode": "structural_slice", "reason": "target_symbol_with_module_imports", "symbols": sorted(symbols & definitions.keys()), "ranges": [{"line_start": start, "line_end": end} for start, end in ranges], "content": content, "slice_bytes": len(content.encode())})
    return slices


def _context_common(payload: dict[str, Any], root: Path, explicit_root: bool, selected: dict[str, Any], limit: int) -> dict[str, Any]:
    included = selected["included_files"]
    excluded = selected["excluded_files"]
    data = {
        "contract_version": WAVE2_CONTRACT_VERSION,
        "mode": payload.get("mode", "audit"),
        "task": payload.get("task", ""),
        "repository_root": str(root),
        "repository_root_explicit": explicit_root,
        "target_files": sorted(set(payload.get("target_files", [])) | set(payload.get("named_files", []))),
        "related_files": [item["path"] for item in included if item["relevance_status"] == "deterministic_dependency"],
        "symbols": sorted(set(payload.get("target_symbols", []))),
        "source_slices": _python_slices(root, included, set(payload.get("target_symbols", []))),
        "observed_failures": payload.get("observed_failures", []),
        "included_files": included,
        "excluded_files": excluded,
        "excluded_candidates": excluded,
        "selection_reasons": [
            {"path": item["path"], "reasons": item["selection_reasons"]}
            for item in included
        ],
        "warnings": ([{"code": "legacy_implicit_repository_root"}] if not explicit_root else []),
        "selection_status": selected["selection_status"],
        "expansion_available": selected["expansion_available"],
        "expansion": {"command": "ldw context pack", "available": selected["expansion_available"]},
        "budget": {"max_context_files": limit, "consumed": len(included)},
        "metrics": {
            "eligible_input_bytes": selected["eligible_input_bytes"],
            "selected_bytes": selected["selected_bytes"],
            "context_reduction": selected["context_reduction"],
            "initial_pack_bytes": selected["selected_bytes"],
            "expansion_bytes": 0,
            "total_context_bytes": selected["selected_bytes"],
            "full_candidate_context_avoided_bytes": max(0, selected["eligible_input_bytes"] - selected["selected_bytes"]),
            "initial_pack_tokens": None,
            "expansion_tokens": None,
            "total_context_tokens": None,
            "expansion_count": 0,
            "input_file_count": len(payload.get("files", [])),
            "selected_file_count": len(included),
            "excluded_file_count": len(excluded),
            "sensitive_block_count": sum(item["reason_code"] == "sensitive_path" for item in excluded),
        },
        "unresolved_references": payload.get("unresolved_references", []),
        "constraints": payload.get("constraints", []),
    }
    data["package_hash"] = stable_hash(data)
    return data


def _lineage_findings(item: Any, index: int, root: Path) -> list[str]:
    prefix = f"evidence_items[{index}]"
    if not isinstance(item, dict):
        return [f"{prefix}:not_object"]
    findings: list[str] = []
    required = {"evidence_type", "source_tool", "source_run_id", "source_type", "source_path", "event_id", "test_run_id", "git_observation_id", "origin", "value"}
    for key in sorted(required - set(item)):
        findings.append(f"{prefix}:missing_{key}")
    if item.get("origin") not in WAVE2_ORIGINS:
        findings.append(f"{prefix}:invalid_origin")
    source_path = item.get("source_path")
    if source_path is not None:
        path, issue = _safe_relative_path(root, source_path)
        if issue or path is None:
            findings.append(f"{prefix}:unsafe_source_path")
        elif _is_sensitive_path(path):
            findings.append(f"{prefix}:sensitive_source_path")
    evidence_type = item.get("evidence_type")
    if evidence_type == "test_status" and (
        item.get("source_tool") != "test_result_parser" or not item.get("source_run_id") or not item.get("test_run_id")
    ):
        findings.append(f"{prefix}:test_status_requires_ldw_test_parse")
    if evidence_type == "git_state" and not (
        item.get("source_tool") == "git_facts_collector" or item.get("origin") == "user-provided"
    ):
        findings.append(f"{prefix}:git_state_requires_ldw_git_facts_or_user")
    if evidence_type == "git_state" and not item.get("git_observation_id"):
        findings.append(f"{prefix}:missing_git_observation_id")
    if evidence_type == "error_group" and item.get("origin") == "model-derived-candidate" and not item.get("source_run_id"):
        findings.append(f"{prefix}:missing_model_source_run_id")
    if evidence_type == "root_cause" or any(key in item for key in ("root_cause", "conclusion")):
        findings.append(f"{prefix}:unsupported_conclusion")
    return findings


def evidence_build(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    try:
        root, explicit_root = _wave2_root(payload)
    except (FileNotFoundError, OSError, ValueError) as exc:
        return result("evidence_package_builder", "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_repository_root", "detail": str(exc)}])
    required = ["task", "repository_state", "observed_log_events", "observed_test_results", "file_inventory"]
    missing = [name for name in required if name not in payload]
    evidence = {name: payload.get(name, [] if name != "task" else "") for name in required}
    evidence.update({
        "contract_version": WAVE2_CONTRACT_VERSION,
        "repository_root": str(root),
        "repository_root_explicit": explicit_root,
        "constraints": payload.get("constraints", []),
        "warnings": payload.get("warnings", []),
        "missing_evidence": sorted(set(missing + payload.get("missing_evidence", []))),
        "open_questions": payload.get("open_questions", []),
        "tool_versions": payload.get("tool_versions", {"local_developer_worker": "0.1.0"}),
        "context_package_reference": payload.get("context_package_reference"),
        "relevant_files": payload.get("relevant_files", []),
    })
    all_events = evidence["observed_log_events"]
    if not isinstance(all_events, list):
        return result("evidence_package_builder", "stdin", raw, {}, status="invalid_input", errors=[{"code": "observed_log_events_must_be_list"}])
    ids = [event.get("event_id") for event in all_events if isinstance(event, dict)]
    duplicate_ids = sorted({item for item in ids if item and ids.count(item) > 1})
    if duplicate_ids:
        return result("evidence_package_builder", "stdin", raw, {}, status="invalid_input", errors=[{"code": "duplicate_evidence_id", "ids": duplicate_ids}])
    invalid_events = []
    for event in all_events:
        if not isinstance(event, dict) or not event.get("event_id"):
            invalid_events.append("missing_event_id"); continue
        source_hash = event.get("raw_hash")
        start, end = event.get("raw_line_start"), event.get("raw_line_end")
        if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash): invalid_events.append(event["event_id"])
        if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start: invalid_events.append(event["event_id"])
    if invalid_events:
        return result("evidence_package_builder", "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_evidence_reference", "items": sorted(set(invalid_events))}])
    evidence_items = payload.get("evidence_items", [])
    if not isinstance(evidence_items, list):
        return result("evidence_package_builder", "stdin", raw, {}, status="invalid_input", errors=[{"code": "evidence_items_must_be_list"}])
    lineage_findings = [finding for index, item in enumerate(evidence_items) for finding in _lineage_findings(item, index, root)]
    if any(finding.endswith(("unsafe_source_path", "sensitive_source_path", "unsupported_conclusion")) for finding in lineage_findings):
        return result("evidence_package_builder", "stdin", raw, {}, status="invalid_input", errors=[{"code": "unsafe_or_unsupported_evidence", "findings": lineage_findings}])
    evidence["evidence_items"] = evidence_items
    evidence["lineage_complete"] = bool(evidence_items) and not lineage_findings
    evidence["lineage_findings"] = lineage_findings
    evidence["observed_facts"] = [item for item in evidence_items if item.get("origin") in {"observed", "user-provided"}]
    evidence["deterministic_derived"] = [item for item in evidence_items if item.get("origin") == "deterministic-derived"]
    evidence["model_derived_candidates"] = [item for item in evidence_items if item.get("origin") == "model-derived-candidate"]
    evidence["test_statuses"] = [item for item in evidence_items if item.get("evidence_type") == "test_status"]
    evidence["error_groups"] = [item for item in evidence_items if item.get("evidence_type") == "error_group"]
    evidence["git_state"] = [item for item in evidence_items if item.get("evidence_type") == "git_state"]
    if not evidence["test_statuses"]:
        evidence["missing_evidence"] = sorted(set(evidence["missing_evidence"] + ["tests: NOT RUN"]))
    files_considered = payload.get("files_already_considered")
    if files_considered is None and isinstance(evidence["file_inventory"], list):
        files_considered = [item.get("path") for item in evidence["file_inventory"] if isinstance(item, dict) and item.get("path")]
    evidence["resume_state"] = {
        "objective": evidence["task"],
        "current_observed_state": payload.get("current_observed_state", "unknown"),
        "files_already_considered": sorted(set(files_considered or [])),
        "tests_actually_observed": evidence["test_statuses"],
        "known_failures": [item for item in evidence_items if item.get("evidence_type") in {"log_event", "error_group"}],
        "constraints": evidence["constraints"],
        "missing_evidence": evidence["missing_evidence"],
        "next_bounded_action": payload.get("next_bounded_action", "unknown"),
    }
    evidence["content_hash"] = stable_hash(evidence)
    partial = bool(evidence["missing_evidence"] or lineage_findings or not explicit_root)
    warnings = ([{"code": "legacy_implicit_repository_root"}] if not explicit_root else [])
    return result("evidence_package_builder", "stdin", raw, {"evidence_package": evidence}, status="partial" if partial else "success", warnings=warnings)


def context_pack(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    try:
        root, explicit_root = _wave2_root(payload)
        limit = int(payload.get("max_context_files", 20))
        if limit < 1:
            raise ValueError("max_context_files must be positive")
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        return result("context_packer", "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_context_input", "detail": str(exc)}])
    mode = payload.get("mode", "audit")
    if mode not in {"audit", "context", "expand"}:
        return result("context_packer", "stdin", raw, {}, status="invalid_input", errors=[{"code": "unsupported_context_mode"}])
    if mode == "expand":
        previous = payload.get("previous_package")
        previous_run_id = payload.get("previous_run_id")
        requested_paths = payload.get("requested_paths", [])
        reason = payload.get("reason")
        trigger = payload.get("deterministic_trigger")
        if not isinstance(previous, dict) or not isinstance(previous_run_id, str) or previous.get("run_id") != previous_run_id:
            return result("context_packer", "stdin", raw, {}, status="invalid_input", errors=[{"code": "previous_package_link_required"}])
        if not isinstance(requested_paths, list) or not all(isinstance(path, str) for path in requested_paths):
            return result("context_packer", "stdin", raw, {}, status="invalid_input", errors=[{"code": "requested_paths_must_be_list"}])
        if not (isinstance(reason, str) and reason.strip()) and not (isinstance(trigger, str) and trigger.strip()):
            return result("context_packer", "stdin", raw, {}, status="invalid_input", errors=[{"code": "expansion_reason_or_trigger_required"}])
        previous_data = previous.get("data") if isinstance(previous.get("data"), dict) else previous
        previous_included = previous_data.get("included_files", [])
        if not isinstance(previous_included, list):
            return result("context_packer", "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_previous_package"}])
        previous_depth = previous_data.get("expansion_depth", 0)
        max_depth = payload.get("max_expansion_depth", DEFAULT_MAX_EXPANSION_DEPTH)
        if not isinstance(previous_depth, int) or previous_depth < 0 or not isinstance(max_depth, int) or max_depth < 1:
            return result("context_packer", "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_expansion_bound"}])
        if previous_depth >= max_depth:
            return result("context_packer", "stdin", raw, {}, status="partial", errors=[{"code": "expansion_depth_limit_reached", "max_expansion_depth": max_depth}])
        try:
            selected = _select_context(payload, root, max(limit, len(payload.get("files", []))), set(requested_paths))
        except TypeError:
            return result("context_packer", "stdin", raw, {}, status="invalid_input", errors=[{"code": "files_must_be_list"}])
        safe_previous: list[dict[str, Any]] = []
        still_excluded = list(selected["excluded_files"])
        for item in previous_included:
            path = item.get("path") if isinstance(item, dict) else None
            normalized, issue = _safe_relative_path(root, path)
            if issue or normalized is None:
                still_excluded.append(_excluded_file(path or "<invalid>", issue or "unsupported", "expansion_revalidation"))
            elif _is_sensitive_path(normalized):
                still_excluded.append(_excluded_file(normalized, "sensitive_path", "expansion_revalidation"))
            else:
                safe_previous.append(item)
        previous_paths = {item["path"] for item in safe_previous}
        requested_set = set(requested_paths)
        available_slots = max(0, limit - len(previous_paths))
        eligible_added = [item for item in selected["included_files"] if item["path"] in requested_set and item["path"] not in previous_paths]
        added = eligible_added[:available_slots]
        for item in eligible_added[available_slots:]:
            still_excluded.append(_excluded_file(item["path"], "over_context_limit", "max_context_files"))
        combined = safe_previous + added
        data = _context_common(payload, root, explicit_root, selected, limit)
        data.update({
            "mode": "expand",
            "previous_run_id": previous_run_id,
            "previous_context_hash": stable_hash(previous_data),
            "requested_paths": requested_paths,
            "requested_symbols": payload.get("requested_symbols", []),
            "expansion_reason": reason.strip() if isinstance(reason, str) else "",
            "deterministic_trigger": trigger.strip() if isinstance(trigger, str) else "",
            "expansion_depth": previous_depth + 1,
            "max_expansion_depth": max_depth,
            "added_files": added,
            "reused_files": safe_previous,
            "still_excluded": sorted(still_excluded, key=lambda item: (item["path"], item["reason_code"])),
            "included_files": combined,
            "relevant_files": [item["path"] for item in combined],
            "source_slices": _python_slices(root, added, set(payload.get("target_symbols", []))),
        })
        total_bytes = sum(item.get("size_bytes", 0) for item in combined)
        data["metrics"].update({
            "selected_bytes": total_bytes,
            "context_reduction": round((selected["eligible_input_bytes"] - total_bytes) / selected["eligible_input_bytes"], 4) if selected["eligible_input_bytes"] else None,
            "initial_pack_bytes": sum(item.get("size_bytes", 0) for item in safe_previous),
            "expansion_bytes": sum(item.get("size_bytes", 0) for item in added),
            "total_context_bytes": total_bytes,
            "full_candidate_context_avoided_bytes": max(0, selected["eligible_input_bytes"] - total_bytes),
            "expansion_count": previous_depth + 1,
            "selected_file_count": len(combined),
        })
        data["package_hash"] = stable_hash({key: value for key, value in data.items() if key != "package_hash"})
        blocked_requested = requested_set - {item["path"] for item in added} - previous_paths
        status = "partial" if blocked_requested or not explicit_root else "success"
        return result("context_packer", "stdin", raw, data, status=status, warnings=data["warnings"])
    try:
        selected = _select_context(payload, root, limit)
    except TypeError:
        return result("context_packer", "stdin", raw, {}, status="invalid_input", errors=[{"code": "files_must_be_list"}])
    data = _context_common(payload, root, explicit_root, selected, limit)
    if mode == "context":
        data.update({
            "mode": "context",
            "relevant_files": [item["path"] for item in selected["included_files"]],
            "relevant_failures": sorted(payload.get("failure_event_ids", [])),
            "test_status": payload.get("test_status", "unknown"),
            "missing_checks": payload.get("missing_checks", []),
            "evidence_references": sorted(payload.get("evidence_references", [])),
        })
    status = "unsupported" if selected["selection_status"] == "unsupported" else ("partial" if not explicit_root else "success")
    return result("context_packer", "stdin", raw, data, status=status, warnings=data["warnings"])


def context_route(payload: dict[str, Any]) -> dict[str, Any]:
    """Choose a deterministic, bounded retrieval plan without reading repository content."""
    raw = canonical_json(payload)
    named = sorted(set(payload.get("target_files", [])) | set(payload.get("named_files", [])))
    symbols = sorted(set(payload.get("target_symbols", [])))
    failures = sorted(set(payload.get("failure_files", [])))
    task = payload.get("task", "")
    if not isinstance(task, str) or not all(isinstance(items, list) and all(isinstance(item, str) for item in items) for items in (named, symbols, failures)):
        return result("context_router", "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_routing_signals"}])
    docs_only = bool(named) and all(path.startswith("docs/") or path.lower().endswith((".md", ".rst")) for path in named)
    if len(named) == 1 and not symbols and not failures:
        strategy, reason, calls = "direct_bounded_read", "one_explicit_file", 1
    elif symbols and named:
        strategy, reason, calls = "structural_symbol_slice", "explicit_symbol_and_file", 1
    elif failures:
        strategy, reason, calls = "focused_failure_neighborhood", "observed_failure_file", 2
    elif docs_only:
        strategy, reason, calls = "docs_and_referenced_contracts", "explicit_docs_only", 1
    else:
        strategy, reason, calls = "inventory_then_context_pack", "ambiguous_or_multifile_task", 2
    return result("context_router", "stdin", raw, {
        "strategy": strategy,
        "reason": reason,
        "target_files": named,
        "target_symbols": symbols,
        "failure_files": failures,
        "planned_tool_calls": calls,
        "fallback": strategy == "inventory_then_context_pack",
        "repository_content_read": False,
    })


def report_summarize(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    package = payload.get("evidence_package")
    if not isinstance(package, dict):
        return result("change_summarizer", "stdin", raw, {}, status="invalid_input", errors=[{"code": "evidence_package_required"}])
    semantic_candidates = payload.get("semantic_candidates")
    semantic_fields = {"group_id", "pattern", "classification", "source_span", "confidence", "origin", "needs_review"}
    def valid_semantic_group(group: Any) -> bool:
        if not isinstance(group, dict) or set(group) != semantic_fields or group.get("origin") != "model-derived":
            return False
        spans = group.get("source_span")
        confidence = group.get("confidence")
        return (
            isinstance(group.get("group_id"), str) and bool(re.fullmatch(r"SG-[A-Z0-9_-]+", group["group_id"]))
            and all(isinstance(group.get(field), str) and bool(group[field]) for field in ("pattern", "classification"))
            and isinstance(spans, list) and bool(spans) and len(spans) == len(set(spans))
            and all(isinstance(event_id, str) and bool(re.fullmatch(r"EV-\d{6}", event_id)) for event_id in spans)
            and isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and 0 <= confidence <= 1
            and isinstance(group.get("needs_review"), bool)
        )
    if semantic_candidates is not None and (
        not isinstance(semantic_candidates, list)
        or any(not valid_semantic_group(group) for group in semantic_candidates)
    ):
        return result("change_summarizer", "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_semantic_candidates"}])
    repo = package.get("repository_state", {})
    tests = package.get("observed_test_results", [])
    facts = {
        "summary": "Facts-only report generated from evidence package.",
        "files_changed": repo.get("changed_files", []),
        "commands_observed": repo.get("command_evidence", []),
        "tests_observed": tests,
        "missing_checks": package.get("missing_evidence", []),
        "warnings": package.get("warnings", []),
        "residual_risks": ["Evidence is partial" ] if package.get("missing_evidence") else [],
        "rollback_facts": {"working_tree_clean": repo.get("working_tree_clean", "unknown")},
        "acceptance_evidence": {"content_hash": package.get("content_hash")},
    }
    if semantic_candidates is not None:
        facts["semantic_candidates"] = semantic_candidates
    return result("change_summarizer", "stdin", raw, facts, status="partial" if package.get("missing_evidence") else "success")


def doctor(payload: dict[str, Any]) -> dict[str, Any]:
    from .policy import load_policy
    raw = canonical_json(payload)
    policy = load_policy(payload.get("policy_path"))
    data = {"python": os.sys.version.split()[0], "network_access": policy.get("network_access"), "profile": policy.get("profile"), "capabilities": policy.get("automatic", {}), "semantic_enabled": policy.get("semantic", {}).get("enabled", False), "test_status_reminder": TEST_STATUS_REMINDER}
    return result("doctor", "local", raw, data)


def benchmark_run(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        return result("benchmark", "stdin", raw, {}, status="invalid_input", errors=[{"code": "cases_must_be_list"}])
    incomplete = [case.get("id", "unknown") for case in cases if not case.get("completed", False)]
    return result("benchmark", "stdin", raw, {"run_status": "incomplete" if incomplete else "complete", "case_count": len(cases), "incomplete_cases": incomplete, "metrics": payload.get("metrics", {})}, status="partial" if incomplete else "success")
