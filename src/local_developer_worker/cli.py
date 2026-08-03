from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

from .contracts import canonical_json, result, valid_tool_result
from .policy import allowed, load_policy, root_allowed
from .portfolio import portfolio_status, portfolio_verify
from .session_log import append_event
from .telemetry import telemetry_event, telemetry_summary
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
    ("telemetry", "summary"): telemetry_summary,
    ("portfolio", "verify"): portfolio_verify,
    ("portfolio", "status"): portfolio_status,
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
    telemetry = sub.add_parser("telemetry").add_subparsers(dest="action", required=True).add_parser("summary")
    telemetry.add_argument("--from-date", dest="date_from")
    telemetry.add_argument("--to-date", dest="date_to")
    portfolio = sub.add_parser("portfolio").add_subparsers(dest="action", required=True)
    verify = portfolio.add_parser("verify")
    verify.add_argument("--only", action="append")
    portfolio.add_parser("status")
    return parser


def _context_reduction(key: tuple[str, ...], payload: dict, output: dict) -> tuple[str, float | None]:
    tool = " ".join(key)
    if key != ("context", "pack") or payload.get("mode") != "context":
        return tool, None
    files = payload.get("files", [])
    if not files or not all(isinstance(item, dict) and isinstance(item.get("size_bytes"), int) for item in files):
        return f"{tool}/context", None
    total = sum(item["size_bytes"] for item in files)
    selected = set(output.get("data", {}).get("relevant_files", []))
    selected_bytes = sum(item["size_bytes"] for item in files if item.get("path") in selected)
    return f"{tool}/context", round((total - selected_bytes) / total, 4) if total else None


def _emit(output: dict, key: tuple[str, ...], payload: dict, raw: str, started: float) -> int:
    stdout_text = canonical_json(output) + "\n"
    if os.environ.get("LDW_TELEMETRY_DISABLED") != "1" and (
        "PYTEST_CURRENT_TEST" not in os.environ or os.environ.get("LDW_TELEMETRY_FORCE") == "1"
    ):
        telemetry_tool, context_reduction = _context_reduction(key, payload, output)
        event = telemetry_event(
            {
                "tool": telemetry_tool,
                "input_bytes": len(raw.encode("utf-8")),
                "output_bytes": len(stdout_text.encode("utf-8")),
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "status": output["status"],
                "fallback_used": bool(output.get("data", {}).get("fallback")),
                "context_reduction": context_reduction,
                "run_id": output["run_id"],
            }
        )
        try:
            append_event(event)
        except (OSError, ValueError):
            print("telemetry_write_failed", file=sys.stderr)
    sys.stdout.write(stdout_text)
    return 0 if output["status"] in {"success", "partial", "unsupported"} else 2


def main(argv: list[str] | None = None) -> int:
    started = time.perf_counter()
    args = _parser().parse_args(argv)
    key = (args.tool,) if args.tool == "doctor" else (args.tool, args.action)
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict): raise ValueError("input must be a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        output = result(" ".join(key), "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_json", "detail": str(exc)}])
        return _emit(output, key, {}, raw, started)
    cli_values = {
        name: getattr(args, name, None)
        for name in ("date_from", "date_to", "only")
        if getattr(args, name, None) is not None
    }
    for name, value in cli_values.items():
        if name in payload and payload[name] != value:
            output = result(" ".join(key), "stdin", raw, {}, status="invalid_input", errors=[{"code": "conflicting_cli_option", "option": name}])
            return _emit(output, key, payload, raw, started)
        payload[name] = value
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
    return _emit(output, key, payload, raw, started)


if __name__ == "__main__":
    raise SystemExit(main())
