from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from .contracts import SourceReference, canonical_json, manifest, result, sha256, stable_hash

SECRET_NAME = re.compile(r"(^|/)(\.env(?:\..*)?|.*(?:secret|credential|password|token|private[_-]?key).*)(?:$|/)", re.I)
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
PY_LOCATION = re.compile(r'File "(?P<file>[^\"]+)", line (?P<line>\d+)')
PYTEST_FAILURE = re.compile(r"^FAILED\s+(?P<test>\S+)")
PYTEST_PASS = re.compile(r"^PASSED\s+(?P<test>\S+)")
PYTEST_OTHER = re.compile(r"^(?P<state>SKIPPED|XFAIL|XPASS|ERROR)\s+(?P<test>\S+)")
DOCKER_ERROR = re.compile(r"(?:ERROR|error|failed|Exited \(\d+\))", re.I)


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
        elif "docker" in clean.lower() or DOCKER_ERROR.search(clean):
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
    elif exit_code == 124 or "timeout" in lowered:
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
        sensitive = bool(SECRET_NAME.search(relative))
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


def evidence_build(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    required = ["task", "repository_state", "observed_log_events", "observed_test_results", "file_inventory"]
    missing = [name for name in required if name not in payload]
    evidence = {name: payload.get(name, [] if name != "task" else "") for name in required}
    evidence.update({"constraints": payload.get("constraints", []), "warnings": payload.get("warnings", []), "missing_evidence": missing + payload.get("missing_evidence", []), "open_questions": payload.get("open_questions", []), "tool_versions": payload.get("tool_versions", {"local_developer_worker": "0.1.0"})})
    all_events = evidence["observed_log_events"]
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
    evidence["content_hash"] = stable_hash(evidence)
    return result("evidence_package_builder", "stdin", raw, {"evidence_package": evidence}, status="partial" if evidence["missing_evidence"] else "success")


def context_pack(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    files = payload.get("files", [])
    if not isinstance(files, list):
        return result("context_packer", "stdin", raw, {}, status="invalid_input", errors=[{"code": "files_must_be_list"}])
    limit = int(payload.get("max_context_files", 20))
    named, changed = set(payload.get("named_files", [])), set(payload.get("changed_files", []))
    failure_files = set(payload.get("failure_files", []))
    import_edges = payload.get("import_edges", {})
    related_imports = {target for origin, targets in import_edges.items() if origin in named | changed | failure_files for target in targets}
    candidates, seen = [], set()
    for item in files:
        path = item.get("path") if isinstance(item, dict) else str(item)
        if not path: continue
        if path in seen:
            candidates.append({"path": path, "included": False, "reason": "duplicate_path"}); continue
        seen.add(path)
        reasons = []
        if path in named: reasons.append("explicitly_named")
        if path in changed: reasons.append("changed_file")
        if path in failure_files: reasons.append("failure_source")
        if path in related_imports: reasons.append("direct_import")
        if path.startswith("tests/"):
            test_relative = Path(path).relative_to("tests")
            source_relatives = {test_relative}
            if test_relative.name.startswith("test_"):
                source_relatives.add(test_relative.with_name(test_relative.name.removeprefix("test_")))
            related_sources = {Path("src", relative).as_posix() for relative in source_relatives}
            if related_sources & (named | changed | failure_files):
                reasons.append("related_test")
        if item.get("potentially_sensitive") if isinstance(item, dict) else False:
            candidates.append({"path": path, "included": False, "reason": "sensitive_blocked"}); continue
        if reasons: candidates.append({"path": path, "included": True, "reasons": reasons})
        else: candidates.append({"path": path, "included": False, "reason": "no_deterministic_signal"})
    ranked = sorted((c for c in candidates if c["included"]), key=lambda c: (-len(c["reasons"]), c["path"]))
    included = ranked[:limit]
    excluded = [c for c in candidates if not c["included"]] + [{"path": c["path"], "included": False, "reason": "context_budget"} for c in ranked[limit:]]
    audit = {"mode": "audit", "included_files": included, "excluded_candidates": excluded, "budget": {"max_context_files": limit, "consumed": len(included)}, "unresolved_references": payload.get("unresolved_references", []), "expansion": {"command": "ldw context pack", "available": bool(ranked[limit:])}}
    if payload.get("mode", "audit") == "context":
        return result("context_packer", "stdin", raw, {"mode": "context", "task": payload.get("task"), "relevant_files": [item["path"] for item in included], "relevant_failures": sorted(payload.get("failure_event_ids", [])), "test_status": payload.get("test_status", "unknown"), "constraints": payload.get("constraints", []), "missing_checks": payload.get("missing_checks", []), "evidence_references": sorted(payload.get("evidence_references", [])), "expansion": audit["expansion"]})
    return result("context_packer", "stdin", raw, audit)


def report_summarize(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    package = payload.get("evidence_package")
    if not isinstance(package, dict):
        return result("change_summarizer", "stdin", raw, {}, status="invalid_input", errors=[{"code": "evidence_package_required"}])
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
    return result("change_summarizer", "stdin", raw, facts, status="partial" if package.get("missing_evidence") else "success")


def doctor(payload: dict[str, Any]) -> dict[str, Any]:
    from .policy import load_policy
    raw = canonical_json(payload)
    policy = load_policy(payload.get("policy_path"))
    data = {"python": os.sys.version.split()[0], "network_access": policy.get("network_access"), "profile": policy.get("profile"), "capabilities": policy.get("automatic", {}), "semantic_enabled": policy.get("semantic", {}).get("enabled", False)}
    return result("doctor", "local", raw, data)


def benchmark_run(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        return result("benchmark", "stdin", raw, {}, status="invalid_input", errors=[{"code": "cases_must_be_list"}])
    incomplete = [case.get("id", "unknown") for case in cases if not case.get("completed", False)]
    return result("benchmark", "stdin", raw, {"run_status": "incomplete" if incomplete else "complete", "case_count": len(cases), "incomplete_cases": incomplete, "metrics": payload.get("metrics", {})}, status="partial" if incomplete else "success")
