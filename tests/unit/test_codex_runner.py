from __future__ import annotations

import json
import subprocess
from pathlib import Path

from local_developer_worker.codex_runner import build_exec_argv, codex_run, parse_codex_jsonl
from local_developer_worker.codex_routing import route_task, validate_codex_policy


def codex_policy(executable: str = "/usr/bin/true") -> dict:
    return {
        "network_access": True,
        "codex": {
            "enabled": True,
            "adaptive_routing": True,
            "allow_profile_downgrade": False,
            "allow_write": False,
            "allow_network": True,
            "default_profile": "balanced",
            "risk_floor": "efficient",
            "maximum_profile": "frontier",
            "executable": executable,
            "allowed_executables": [executable],
            "verification_executables": ["/usr/bin/true"],
            "verification_commands": [["/usr/bin/true"]],
            "environment_allowlist": ["PATH"],
            "supported_cli_versions": ["0.147"],
            "sandbox": "read-only",
            "approval_policy": "never",
            "max_escalations": 2,
            "timeout_seconds": 60,
            "verification_timeout_seconds": 30,
            "max_output_bytes": 100000,
            "max_task_bytes": 100000,
            "retriable_error_codes": ["timeout", "provider_failed"],
            "profiles": {
                "efficient": {"alias": "small", "effort": "low"},
                "balanced": {"alias": "standard", "effort": "medium"},
                "frontier": {"alias": "large", "effort": "high"},
            },
            "aliases": {
                "small": {"model": "model-a", "supported_efforts": ["low"], "fallback_aliases": []},
                "standard": {"model": "model-b", "supported_efforts": ["medium"], "fallback_aliases": []},
                "large": {"model": "model-c", "supported_efforts": ["high"], "fallback_aliases": []},
            },
            "escalation": {"efficient": "balanced", "balanced": "frontier"},
        }
    }


def _git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def _completed(argv, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(argv, returncode, stdout, stderr)


def _jsonl(*events):
    return "\n".join(json.dumps(event) for event in events) + "\n"


HELP_TEXT = "--json --strict-config --ignore-user-config --ignore-rules --model --sandbox --cd --last"


def test_argv_carries_resolved_model_effort_and_isolation(tmp_path):
    executable = tmp_path / "codex"
    executable.write_text("fake")
    executable.chmod(0o700)
    config = validate_codex_policy(codex_policy(str(executable)))
    route = route_task("Fix a bug", {}, config)
    argv = build_exec_argv(route, config, str(tmp_path))
    assert argv[0:2] == [str(executable), "exec"]
    assert argv[argv.index("-m") + 1] == "model-b"
    assert 'model_reasoning_effort="medium"' in argv
    assert 'sandbox_mode="read-only"' in argv
    assert 'approval_policy="never"' in argv
    assert "--ignore-user-config" in argv
    assert argv[-3:] == ["-C", str(tmp_path), "-"]


def test_jsonl_parser_keeps_only_bounded_observation():
    observation = parse_codex_jsonl(
        _jsonl(
            {"type": "thread.started", "thread_id": "secret-thread"},
            {"type": "item.completed", "item": {"type": "file_change", "changes": "secret source"}},
            {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 3}},
        )
    )
    assert observation.completed is True
    assert observation.thread_id == "secret-thread"
    assert observation.mutation_observed is True
    assert observation.tokens["input_tokens"] == 10
    assert not hasattr(observation, "provider_response")


def test_success_does_not_escalate(tmp_path):
    executable = tmp_path / "codex"
    executable.write_text("fake")
    executable.chmod(0o700)
    _git_repo(tmp_path)
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        if argv[1:] == ["--version"]:
            return _completed(argv, stdout="codex-cli 0.147.0")
        if argv[-1:] == ["--help"]:
            return _completed(argv, stdout=HELP_TEXT)
        return _completed(argv, stdout=_jsonl({"type": "thread.started", "thread_id": "thread-1"}, {"type": "turn.completed", "usage": {"input_tokens": 5}}))

    output = codex_run(
        {"task": "Review the README", "repository_root": str(tmp_path), "verification": {"kind": "execution"}},
        codex_policy(str(executable)),
        runner=runner,
    )
    assert output["status"] == "success"
    assert output["data"]["terminal_status"] == "pass"
    assert output["data"]["escalation_count"] == 0
    assert len(calls) == 4


def test_verified_failure_resumes_exact_thread_with_stronger_profile(tmp_path):
    executable = tmp_path / "codex"
    executable.write_text("fake")
    executable.chmod(0o700)
    _git_repo(tmp_path)
    codex_attempts = verification_attempts = 0
    observed = []

    def runner(argv, **kwargs):
        nonlocal codex_attempts, verification_attempts
        observed.append((argv, kwargs["input"], kwargs["cwd"]))
        if argv[1:] == ["--version"]:
            return _completed(argv, stdout="codex-cli 0.147.0")
        if argv[-1:] == ["--help"]:
            return _completed(argv, stdout=HELP_TEXT)
        if argv[0] == "/usr/bin/true":
            verification_attempts += 1
            return _completed(argv, returncode=1 if verification_attempts == 1 else 0)
        codex_attempts += 1
        return _completed(argv, stdout=_jsonl({"type": "thread.started", "thread_id": "thread-exact"}, {"type": "turn.completed"}))

    output = codex_run(
        {
            "task": "Fix the bug",
            "repository_root": str(tmp_path),
            "verification": {"kind": "command", "argv": ["/usr/bin/true"]},
        },
        codex_policy(str(executable)),
        runner=runner,
    )
    resume_argv = next(argv for argv, _, _ in observed if "resume" in argv and argv[-1] == "-")
    assert output["status"] == "success"
    assert output["data"]["profile"] == "frontier"
    assert output["data"]["escalation_count"] == 1
    assert "thread-exact" in resume_argv and "--last" not in resume_argv
    assert resume_argv[resume_argv.index("-m") + 1] == "model-c"
    assert 'sandbox_mode="read-only"' in resume_argv
    assert codex_attempts == verification_attempts == 2


def test_model_unavailable_uses_declared_fallback_before_mutation(tmp_path):
    executable = tmp_path / "codex"
    executable.write_text("fake")
    executable.chmod(0o700)
    _git_repo(tmp_path)
    policy = codex_policy(str(executable))
    policy["codex"]["aliases"]["small"]["fallback_aliases"] = ["small-backup"]
    policy["codex"]["aliases"]["small-backup"] = {
        "model": "model-a-backup",
        "supported_efforts": ["low"],
        "fallback_aliases": [],
    }
    attempts = 0

    def runner(argv, **kwargs):
        nonlocal attempts
        if argv[1:] == ["--version"]:
            return _completed(argv, stdout="codex-cli 0.147.0")
        if argv[-1:] == ["--help"]:
            return _completed(argv, stdout=HELP_TEXT)
        attempts += 1
        if attempts == 1:
            return _completed(argv, returncode=1, stdout=_jsonl({"type": "turn.failed", "error": {"code": "model_unavailable"}}))
        return _completed(argv, stdout=_jsonl({"type": "thread.started", "thread_id": "thread-2"}, {"type": "turn.completed"}))

    output = codex_run(
        {"task": "Review documentation", "repository_root": str(tmp_path), "verification": {"kind": "execution"}},
        policy,
        runner=runner,
    )
    assert output["status"] == "success"
    assert output["data"]["model_alias"] == "small-backup"
    assert output["data"]["fallback_count"] == 1
    assert output["data"]["escalation_count"] == 0


def test_mutation_task_requires_explicit_verifier(tmp_path):
    executable = tmp_path / "codex"
    executable.write_text("fake")
    executable.chmod(0o700)
    output = codex_run({"task": "Fix bug", "repository_root": str(tmp_path)}, codex_policy(str(executable)), runner=lambda *args, **kwargs: None)
    assert output["status"] == "policy_blocked"
    assert output["errors"][0]["code"] == "verification_required"


def test_failed_verification_without_thread_id_never_retries_and_preserves_dirty_tree(tmp_path):
    executable = tmp_path / "codex"
    executable.write_text("fake")
    executable.chmod(0o700)
    _git_repo(tmp_path)
    dirty = tmp_path / "user-work.txt"
    dirty.write_text("keep me")
    codex_attempts = 0

    def runner(argv, **kwargs):
        nonlocal codex_attempts
        if argv[1:] == ["--version"]:
            return _completed(argv, stdout="codex-cli 0.147.0")
        if argv[-1:] == ["--help"]:
            return _completed(argv, stdout=HELP_TEXT)
        if argv[0] == "/usr/bin/true":
            return _completed(argv, returncode=1)
        codex_attempts += 1
        return _completed(argv, stdout=_jsonl({"type": "turn.completed"}))

    output = codex_run(
        {
            "task": "Fix the bug",
            "repository_root": str(tmp_path),
            "verification": {"kind": "command", "argv": ["/usr/bin/true"]},
        },
        codex_policy(str(executable)),
        runner=runner,
    )
    assert output["data"]["terminal_status"] == "failed"
    assert output["data"]["escalation_count"] == 0
    assert codex_attempts == 1
    assert dirty.read_text() == "keep me"


def test_escalation_budget_is_a_hard_limit(tmp_path):
    executable = tmp_path / "codex"
    executable.write_text("fake")
    executable.chmod(0o700)
    _git_repo(tmp_path)
    policy = codex_policy(str(executable))
    policy["codex"]["max_escalations"] = 1
    attempts = 0

    def runner(argv, **kwargs):
        nonlocal attempts
        if argv[1:] == ["--version"]:
            return _completed(argv, stdout="codex-cli 0.147.0")
        if argv[-1:] == ["--help"]:
            return _completed(argv, stdout=HELP_TEXT)
        if argv[0] == "/usr/bin/true":
            return _completed(argv, returncode=1)
        attempts += 1
        return _completed(argv, stdout=_jsonl({"type": "thread.started", "thread_id": "bounded-thread"}, {"type": "turn.completed"}))

    output = codex_run(
        {
            "task": "Fix the bug",
            "repository_root": str(tmp_path),
            "verification": {"kind": "command", "argv": ["/usr/bin/true"]},
        },
        policy,
        runner=runner,
    )
    assert output["data"]["terminal_status"] == "failed"
    assert output["data"]["escalation_count"] == 1
    assert attempts == 2


def test_symlinked_codex_and_unlisted_verifier_fail_closed(tmp_path):
    _git_repo(tmp_path)
    target = tmp_path / "codex-real"
    target.write_text("fake")
    target.chmod(0o700)
    executable = tmp_path / "codex-link"
    executable.symlink_to(target)
    policy = codex_policy(str(executable))
    policy["codex"]["allowed_executables"] = [str(target)]
    blocked = codex_run(
        {"task": "Review docs", "repository_root": str(tmp_path), "verification": {"kind": "execution"}},
        policy,
        runner=lambda *args, **kwargs: _completed(args[0]),
    )
    assert blocked["status"] == "policy_blocked"
    assert blocked["errors"][0]["code"] == "codex_executable_not_allowed"

    direct_policy = codex_policy(str(target))
    rejected_verifier = codex_run(
        {
            "task": "Fix bug",
            "repository_root": str(tmp_path),
            "verification": {"kind": "command", "argv": ["/usr/bin/true", "extra"]},
        },
        direct_policy,
        runner=lambda *args, **kwargs: _completed(args[0]),
    )
    assert rejected_verifier["status"] == "policy_blocked"
    assert rejected_verifier["errors"][0]["code"] == "verification_command_not_allowed"
