from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .codex_routing import PROFILE_RANK, CodexConfigError, Route, route_for_profile, route_task, validate_codex_policy
from .contracts import canonical_json, result
from .tools import git_facts, parse_tests

ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]
MODEL_UNAVAILABLE_CODES = frozenset({"model_not_found", "model_unavailable", "unsupported_model"})
MUTATION_ITEM_TYPES = frozenset({"file_change", "command_execution"})
EXEC_CAPABILITIES = ("--json", "--strict-config", "--ignore-user-config", "--ignore-rules", "--model", "--sandbox", "--cd")
RESUME_CAPABILITIES = ("--json", "--strict-config", "--ignore-user-config", "--ignore-rules", "--model", "--last")
RESUME_INSTRUCTION = (
    "Verification did not pass. Inspect the current authorized repository state, "
    "address the verified failure, and complete the original task."
)


@dataclass(frozen=True)
class Observation:
    completed: bool
    thread_id: str | None
    error_code: str | None
    mutation_observed: bool
    tokens: dict[str, int | None]


def _default_runner(
    argv: list[str],
    *,
    input: str,
    cwd: str,
    timeout: int,
    env: dict[str, str],
    max_output_bytes: int,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=env,
        start_new_session=True,
    )
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    try:
        input_bytes = input.encode("utf-8")
        input_offset = 0
        streams = {process.stdout: bytearray(), process.stderr: bytearray()}
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        if input_bytes:
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
        else:
            process.stdin.close()
        deadline = time.monotonic() + timeout
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(argv, timeout)
            for key, _ in selector.select(remaining):
                if key.data == "stdin":
                    try:
                        input_offset += os.write(key.fileobj.fileno(), input_bytes[input_offset:])
                    except BrokenPipeError:
                        input_offset = len(input_bytes)
                    if input_offset >= len(input_bytes):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    continue
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                streams[key.fileobj].extend(chunk)
                if sum(len(value) for value in streams.values()) > max_output_bytes:
                    raise CodexConfigError("codex_output_limit_exceeded")
        returncode = process.wait(timeout=max(0.01, deadline - time.monotonic()))
        return subprocess.CompletedProcess(
            argv,
            returncode,
            bytes(streams[process.stdout]).decode("utf-8", errors="replace"),
            bytes(streams[process.stderr]).decode("utf-8", errors="replace"),
        )
    except (CodexConfigError, OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        raise


def _safe_environment(config: dict[str, Any]) -> dict[str, str]:
    return {name: os.environ[name] for name in config["environment_allowlist"] if name in os.environ}


def _run(
    runner: ProcessRunner,
    argv: list[str],
    *,
    stdin: str,
    root: str,
    timeout: int,
    config: dict[str, Any],
) -> subprocess.CompletedProcess[str]:
    completed = runner(
        argv,
        input=stdin,
        cwd=root,
        timeout=timeout,
        env=_safe_environment(config),
        max_output_bytes=config["max_output_bytes"],
    )
    stdout = completed.stdout if isinstance(completed.stdout, str) else ""
    stderr = completed.stderr if isinstance(completed.stderr, str) else ""
    if len(stdout.encode("utf-8")) + len(stderr.encode("utf-8")) > config["max_output_bytes"]:
        raise CodexConfigError("codex_output_limit_exceeded")
    return completed


def _executable_preflight(config: dict[str, Any], root: str, runner: ProcessRunner) -> None:
    executable = Path(config["executable"])
    try:
        resolved = executable.resolve(strict=True)
    except OSError as exc:
        raise CodexConfigError("codex_executable_unavailable") from exc
    if executable.is_symlink() or resolved != executable or str(resolved) not in config["allowed_executables"] or not os.access(resolved, os.X_OK):
        raise CodexConfigError("codex_executable_not_allowed")
    try:
        version = _run(runner, [str(resolved), "--version"], stdin="", root=root, timeout=10, config=config)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CodexConfigError("codex_capability_preflight_failed") from exc
    version_text = (version.stdout or "").strip()
    if version.returncode != 0 or not any(marker in version_text for marker in config["supported_cli_versions"]):
        raise CodexConfigError("codex_capability_preflight_failed")
    for argv, required in (
        ([str(resolved), "exec", "--help"], EXEC_CAPABILITIES),
        ([str(resolved), "exec", "resume", "--help"], RESUME_CAPABILITIES),
    ):
        try:
            help_result = _run(runner, argv, stdin="", root=root, timeout=10, config=config)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CodexConfigError("codex_capability_preflight_failed") from exc
        help_text = help_result.stdout or ""
        if help_result.returncode != 0 or any(marker not in help_text for marker in required):
            raise CodexConfigError("codex_capability_preflight_failed")


def _config_args(route: Route, config: dict[str, Any]) -> list[str]:
    model = config["aliases"][route.model_alias]["model"]
    return [
        "--json",
        "--strict-config",
        "--ignore-user-config",
        "--ignore-rules",
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{route.effort}"',
        "-c",
        f'sandbox_mode="{config["sandbox"]}"',
        "-c",
        f'approval_policy="{config["approval_policy"]}"',
        "-c",
        "sandbox_workspace_write.network_access=false",
    ]


def build_exec_argv(route: Route, config: dict[str, Any], root: str) -> list[str]:
    return [config["executable"], "exec", *_config_args(route, config), "-s", config["sandbox"], "-C", root, "-"]


def build_resume_argv(route: Route, config: dict[str, Any], thread_id: str) -> list[str]:
    return [config["executable"], "exec", "resume", *_config_args(route, config), thread_id, "-"]


def parse_codex_jsonl(text: str) -> Observation:
    completed = False
    thread_id: str | None = None
    error_code: str | None = None
    mutation_observed = False
    tokens: dict[str, int | None] = {
        "input_tokens": None,
        "cached_input_tokens": None,
        "output_tokens": None,
        "reasoning_output_tokens": None,
    }
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type == "thread.started" and isinstance(event.get("thread_id"), str):
            thread_id = event["thread_id"]
        elif event_type == "turn.completed":
            completed = True
            usage = event.get("usage")
            if isinstance(usage, dict):
                for field in tokens:
                    value = usage.get(field)
                    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                        tokens[field] = value
        elif event_type in {"turn.failed", "error"}:
            error = event.get("error")
            code = error.get("code") if isinstance(error, dict) else event.get("code")
            error_code = code if isinstance(code, str) else "provider_failed"
        elif event_type in {"item.started", "item.completed"}:
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") in MUTATION_ITEM_TYPES:
                mutation_observed = True
    return Observation(completed, thread_id, error_code, mutation_observed, tokens)


def _validate_verification(payload: dict[str, Any], route: Route, config: dict[str, Any]) -> dict[str, Any]:
    verification = payload.get("verification", {"kind": "execution"})
    if not isinstance(verification, dict) or verification.get("kind") not in {"execution", "command", "test"}:
        raise CodexConfigError("invalid_verification")
    kind = verification["kind"]
    if kind == "execution":
        if set(verification) != {"kind"}:
            raise CodexConfigError("invalid_verification")
        if route.mutation_capable:
            raise CodexConfigError("verification_required")
        return {"kind": kind}
    if set(verification) != {"kind", "argv"}:
        raise CodexConfigError("invalid_verification")
    argv = verification.get("argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        raise CodexConfigError("invalid_verification")
    executable = Path(argv[0])
    try:
        resolved = executable.resolve(strict=True)
    except OSError as exc:
        raise CodexConfigError("verification_executable_not_allowed") from exc
    if executable.is_symlink() or resolved != executable or str(resolved) not in config["verification_executables"] or not os.access(resolved, os.X_OK):
        raise CodexConfigError("verification_executable_not_allowed")
    if tuple(argv) not in config["verification_commands"]:
        raise CodexConfigError("verification_command_not_allowed")
    return {"kind": kind, "argv": argv}


def _verify(
    verification: dict[str, Any],
    observation: Observation,
    *,
    root: str,
    runner: ProcessRunner,
    config: dict[str, Any],
) -> str:
    if not observation.completed:
        return "not_run"
    if verification["kind"] == "execution":
        return "passed"
    try:
        completed = _run(
            runner,
            verification["argv"],
            stdin="",
            root=root,
            timeout=config["verification_timeout_seconds"],
            config=config,
        )
    except (OSError, subprocess.TimeoutExpired, CodexConfigError):
        return "uncertain"
    combined = "\n".join(part for part in (completed.stdout, completed.stderr) if isinstance(part, str))
    if verification["kind"] == "command":
        return "passed" if completed.returncode == 0 else "failed"
    parsed = parse_tests(
        {
            "text": combined,
            "exit_code": completed.returncode,
            "command_observed": True,
            "source": "codex_verification",
        }
    )
    run_status = parsed.get("data", {}).get("run_status")
    return "passed" if run_status == "passed" else "failed" if run_status in {"failed", "error", "not_collected"} else "uncertain"


def _public_data(route: Route | None, terminal: str, verification: str, fallbacks: int, escalations: int, tokens: dict[str, int | None] | None = None) -> dict[str, Any]:
    token_values = tokens or {
        "input_tokens": None,
        "cached_input_tokens": None,
        "output_tokens": None,
        "reasoning_output_tokens": None,
    }
    return {
        "profile": route.profile if route else None,
        "model_alias": route.model_alias if route else None,
        "effort": route.effort if route else None,
        "routing_signal": route.signal if route else None,
        "routing_confidence": "uncertain" if route and route.uncertain else "certain" if route else None,
        "deterministic_risk_floor": route.deterministic_risk_floor if route else None,
        "policy_revision": route.policy_revision if route else None,
        "terminal_status": terminal,
        "verification_status": verification,
        "fallback_count": fallbacks,
        "escalation_count": escalations,
        **token_values,
    }


def _merge_tokens(total: dict[str, int | None], observed: dict[str, int | None]) -> None:
    for field, value in observed.items():
        if value is not None:
            total[field] = (total[field] or 0) + value


def codex_run(payload: dict[str, Any], policy: dict[str, Any], *, runner: ProcessRunner | None = None) -> dict[str, Any]:
    raw = canonical_json(payload)
    process_runner = runner or _default_runner
    route: Route | None = None
    try:
        config = validate_codex_policy(policy)
        allowed_input_fields = {"task", "repository_root", "policy_path", "task_class", "profile", "verification"}
        if set(payload) - allowed_input_fields:
            raise CodexConfigError("invalid_codex_input", "unknown input fields")
        task = payload.get("task")
        root_value = payload.get("repository_root")
        if not isinstance(root_value, str) or not root_value:
            raise CodexConfigError("invalid_codex_input", "repository_root is required")
        root = str(Path(root_value).resolve(strict=True))
        if not isinstance(task, str) or len(task.encode("utf-8")) > config["max_task_bytes"]:
            raise CodexConfigError("codex_task_size_exceeded")
        route = route_task(task, payload, config)
        verification = _validate_verification(payload, route, config)
        baseline = git_facts({"repository_root": root})
        if baseline["status"] != "success":
            raise CodexConfigError("codex_git_preflight_failed")
        _executable_preflight(config, root, process_runner)
    except (CodexConfigError, FileNotFoundError, OSError) as exc:
        code = exc.code if isinstance(exc, CodexConfigError) else "invalid_codex_input"
        return result(
            "codex_run",
            "stdin",
            raw,
            _public_data(route, "blocked", "not_run", 0, 0),
            status="policy_blocked" if code not in {"invalid_codex_input", "invalid_verification", "codex_task_size_exceeded"} else "invalid_input",
            errors=[{"code": code}],
        )

    fallback_count = escalation_count = 0
    thread_id: str | None = None
    current_route = route
    current_alias = route.model_alias
    fallback_queue = list(config["aliases"][current_alias]["fallback_aliases"])
    fallback_seen = {current_alias}
    resume = False
    tokens: dict[str, int | None] = {
        "input_tokens": None,
        "cached_input_tokens": None,
        "output_tokens": None,
        "reasoning_output_tokens": None,
    }
    while True:
        alias_row = config["aliases"][current_alias]
        attempt_route = Route(
            current_route.profile,
            current_alias,
            current_route.effort,
            current_route.signal,
            current_route.uncertain,
            current_route.mutation_capable,
            current_route.deterministic_risk_floor,
            current_route.policy_revision,
        )
        if attempt_route.effort not in alias_row["supported_efforts"]:
            terminal, verification_status, error_code = "blocked", "not_run", "invalid_codex_config"
            break
        argv = build_resume_argv(attempt_route, config, thread_id) if resume and thread_id else build_exec_argv(attempt_route, config, root)
        stdin = RESUME_INSTRUCTION if resume else payload["task"]
        try:
            completed = _run(process_runner, argv, stdin=stdin, root=root, timeout=config["timeout_seconds"], config=config)
            observation = parse_codex_jsonl(completed.stdout or "")
            if completed.returncode != 0 and observation.error_code is None:
                observation = Observation(
                    False,
                    observation.thread_id,
                    "process_exit_nonzero",
                    observation.mutation_observed,
                    observation.tokens,
                )
        except subprocess.TimeoutExpired:
            observation = Observation(
                False,
                thread_id,
                "timeout",
                False,
                {
                    "input_tokens": None,
                    "cached_input_tokens": None,
                    "output_tokens": None,
                    "reasoning_output_tokens": None,
                },
            )
        except (OSError, CodexConfigError) as exc:
            error_code = exc.code if isinstance(exc, CodexConfigError) else "codex_execution_failed"
            terminal, verification_status = "blocked", "not_run"
            break
        thread_id = observation.thread_id or thread_id
        current_route = attempt_route
        _merge_tokens(tokens, observation.tokens)
        if observation.error_code in MODEL_UNAVAILABLE_CODES and not observation.mutation_observed:
            if fallback_queue:
                current_alias = fallback_queue.pop(0)
                fallback_seen.add(current_alias)
                fallback_queue.extend(
                    alias for alias in config["aliases"][current_alias]["fallback_aliases"]
                    if alias not in fallback_seen and alias not in fallback_queue
                )
                fallback_count += 1
                resume = False
                continue
        verification_status = _verify(verification, observation, root=root, runner=process_runner, config=config)
        if observation.completed and observation.error_code is None and verification_status == "passed":
            terminal, error_code = "pass", None
            break
        evidence_for_escalation = verification_status in {"failed", "uncertain"} or observation.error_code in config["retriable_error_codes"]
        next_profile = config["escalation"].get(current_route.profile)
        if next_profile and PROFILE_RANK[next_profile] > PROFILE_RANK[config["maximum_profile"]]:
            next_profile = None
        if evidence_for_escalation and thread_id and escalation_count < config["max_escalations"] and next_profile:
            current_route = route_for_profile(next_profile, config)
            current_alias = current_route.model_alias
            fallback_queue = list(config["aliases"][current_alias]["fallback_aliases"])
            fallback_seen = {current_alias}
            escalation_count += 1
            resume = True
            continue
        terminal = "failed" if observation.error_code or verification_status == "failed" else "blocked"
        error_code = observation.error_code or ("verification_failed" if verification_status == "failed" else "verification_uncertain")
        break

    post = git_facts({"repository_root": root})
    if post["status"] != "success" and terminal == "pass":
        terminal, verification_status, error_code = "blocked", "uncertain", "codex_git_postflight_failed"
    public = _public_data(current_route, terminal, verification_status, fallback_count, escalation_count, tokens)
    if terminal == "pass":
        return result("codex_run", "stdin", raw, public)
    status = "policy_blocked" if terminal == "blocked" else "partial"
    return result("codex_run", "stdin", raw, public, status=status, errors=[{"code": error_code or "codex_execution_failed"}])
