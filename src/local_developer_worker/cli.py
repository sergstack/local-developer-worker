from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from .contracts import canonical_json, result, valid_tool_result
from .policy import allowed, load_policy, root_allowed
from .tools import benchmark_run, context_pack, doctor, evidence_build, file_inventory, git_facts, parse_log, parse_tests, report_summarize

COMMANDS: dict[tuple[str, ...], Callable[[dict], dict]] = {
    ("doctor",): doctor,
    ("log", "parse"): parse_log,
    ("test", "parse"): parse_tests,
    ("git", "facts"): git_facts,
    ("files", "inventory"): file_inventory,
    ("evidence", "build"): evidence_build,
    ("context", "pack"): context_pack,
    ("report", "summarize"): report_summarize,
    ("benchmark", "run"): benchmark_run,
}
CAPABILITIES = {
    ("log", "parse"): "structured_log_parser", ("test", "parse"): "test_result_parser",
    ("git", "facts"): "git_facts_collector", ("files", "inventory"): "file_inventory",
    ("context", "pack"): "context_packer", ("report", "summarize"): "change_summarizer_facts_only",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ldw", description="Deterministic local developer evidence worker")
    sub = parser.add_subparsers(dest="tool", required=True)
    sub.add_parser("doctor")
    for name, action in [("log", "parse"), ("test", "parse"), ("git", "facts"), ("files", "inventory"), ("evidence", "build"), ("context", "pack"), ("report", "summarize"), ("benchmark", "run")]:
        group = sub.add_parser(name)
        group.add_subparsers(dest="action", required=True).add_parser(action)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    key = (args.tool,) if args.tool == "doctor" else (args.tool, args.action)
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict): raise ValueError("input must be a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        output = result(" ".join(key), "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_json", "detail": str(exc)}])
        print(canonical_json(output)); return 2
    internal_error_fallback = "codex"
    try:
        capability = CAPABILITIES.get(key)
        policy = load_policy(payload.get("policy_path"))
        internal_error_fallback = policy.get("fallback", {}).get("on_internal_error") or "codex"
        limits = policy.get("limits", {})
        max_log_bytes = int(limits.get("max_log_size_mb", 20)) * 1024 * 1024
        timeout_seconds = int(limits.get("timeout_seconds", 60))
        if timeout_seconds <= 0:
            output = result(" ".join(key), "stdin", raw, {"fallback": policy.get("fallback", {}).get("on_timeout", "codex")}, status="timeout", errors=[{"code": "timeout_before_execution"}])
        elif key in {("git", "facts"), ("files", "inventory")} and not root_allowed(policy, str(payload.get("repository_root", "")), Path.cwd()):
            output = result(" ".join(key), "stdin", raw, {"fallback": policy.get("fallback", {}).get("on_policy_violation", "codex")}, status="policy_blocked", errors=[{"code": "repository_root_not_allowed"}])
        elif key == ("log", "parse") and len(raw.encode("utf-8")) > max_log_bytes:
            output = result(" ".join(key), "stdin", raw, {"fallback": policy.get("fallback", {}).get("on_policy_violation", "codex")}, status="policy_blocked", errors=[{"code": "input_size_exceeded", "limit_bytes": max_log_bytes}])
        elif capability and not allowed(policy, capability):
            output = result(" ".join(key), "stdin", raw, {"fallback": policy.get("fallback", {}).get("on_policy_violation", "codex")}, status="policy_blocked", errors=[{"code": "capability_disabled", "capability": capability}])
        else:
            if key == ("context", "pack"):
                payload["max_context_files"] = min(int(payload.get("max_context_files", limits.get("max_context_files", 20))), int(limits.get("max_context_files", 20)))
            output = COMMANDS[key](payload)
        if not valid_tool_result(output):
            output = result(" ".join(key), "stdin", raw, {"fallback": policy.get("fallback", {}).get("on_invalid_schema", "codex")}, status="internal_error", errors=[{"code": "invalid_output_schema"}])
    except (OSError, ValueError):
        output = result(" ".join(key), "stdin", raw, {"fallback": "codex"}, status="policy_blocked", errors=[{"code": "invalid_policy"}])
    except Exception as exc:  # boundary: unexpected errors must still be observable JSON
        output = result(" ".join(key), "stdin", raw, {"fallback": internal_error_fallback}, status="internal_error", errors=[{"code": "internal_error", "detail": str(exc)}])
    print(canonical_json(output))
    return 0 if output["status"] in {"success", "partial", "unsupported"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
