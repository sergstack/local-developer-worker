from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from jsonschema import validate
from local_developer_worker.session_log import iter_records


ROOT = Path(__file__).parents[2]


def _policy(path: Path, executable: Path, repository: Path, *, enabled: bool = True, adaptive: bool = True) -> None:
    path.write_text(
        f'''network_access = true
[security]
allowed_repository_roots = ["{repository}"]
[codex]
enabled = {str(enabled).lower()}
adaptive_routing = {str(adaptive).lower()}
allow_profile_downgrade = false
allow_write = false
allow_network = true
default_profile = "balanced"
risk_floor = "efficient"
maximum_profile = "frontier"
executable = "{executable}"
allowed_executables = ["{executable}"]
verification_executables = ["/usr/bin/true"]
verification_commands = [["/usr/bin/true"]]
environment_allowlist = ["PATH"]
supported_cli_versions = ["0.147"]
sandbox = "read-only"
approval_policy = "never"
max_escalations = 1
timeout_seconds = 30
verification_timeout_seconds = 10
max_output_bytes = 100000
max_task_bytes = 100000
retriable_error_codes = ["timeout"]
[codex.profiles.efficient]
alias = "small"
effort = "low"
[codex.profiles.balanced]
alias = "standard"
effort = "medium"
[codex.profiles.frontier]
alias = "large"
effort = "high"
[codex.aliases.small]
model = "model-a"
supported_efforts = ["low"]
fallback_aliases = []
[codex.aliases.standard]
model = "model-b"
supported_efforts = ["medium"]
fallback_aliases = []
[codex.aliases.large]
model = "model-c"
supported_efforts = ["high"]
fallback_aliases = []
[codex.escalation]
efficient = "balanced"
balanced = "frontier"
'''
    )


def _run(payload: dict, *, telemetry_root: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", "codex", "run"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=ROOT,
        env={
            **os.environ, "PYTHONPATH": str(ROOT / "src"),
            **({"LDW_SESSION_LOG_DIR": str(telemetry_root), "LDW_TELEMETRY_FORCE": "1"} if telemetry_root else {"LDW_TELEMETRY_DISABLED": "1"}),
        },
        check=False,
    )


def _routing_run(action: str, payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", "routing", action],
        input=json.dumps(payload), text=True, capture_output=True, cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "LDW_TELEMETRY_DISABLED": "1"}, check=False,
    )


def test_cli_executes_selected_profile_and_validates_public_schema(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    executable = tmp_path / "fake-codex"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "if sys.argv[1:] == ['--version']:\n"
        " print('codex-cli 0.147.0')\n"
        "elif sys.argv[-1:] == ['--help']:\n"
        " print('--json --strict-config --ignore-user-config --ignore-rules --model --sandbox --cd --last')\n"
        "else:\n"
        " print(json.dumps({'type':'thread.started','thread_id':'ephemeral-test-id'}))\n"
        " print(json.dumps({'type':'turn.completed','usage':{'input_tokens':7,'output_tokens':2}}))\n"
    )
    executable.chmod(0o700)
    policy = tmp_path / "policy.toml"
    _policy(policy, executable, repository)
    completed = _run(
        {
            "task": "Review the README",
            "repository_root": str(repository),
            "policy_path": str(policy),
            "verification": {"kind": "execution"},
        }
    )
    output = json.loads(completed.stdout)
    validate(output["data"], json.loads((ROOT / "schemas/codex_run_data.schema.json").read_text()))
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert output["data"]["profile"] == "efficient"
    assert output["data"]["effort"] == "low"
    assert "ephemeral-test-id" not in completed.stdout


def test_disabled_feature_blocks_without_launch(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    executable = tmp_path / "must-not-run"
    executable.write_text("#!/bin/sh\nexit 99\n")
    executable.chmod(0o700)
    policy = tmp_path / "policy.toml"
    _policy(policy, executable, repository, enabled=False)
    completed = _run({"task": "Review docs", "repository_root": str(repository), "policy_path": str(policy)})
    output = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert output["status"] == "policy_blocked"
    assert output["errors"][0]["code"] == "codex_disabled"


def test_fixed_profile_flag_restores_configured_route(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    executable = tmp_path / "fake-codex"
    executable.write_text(
        "#!/usr/bin/env python3\nimport json, sys\n"
        "print('codex-cli 0.147.0') if sys.argv[1:] == ['--version'] else "
        "print('--json --strict-config --ignore-user-config --ignore-rules --model --sandbox --cd --last') if sys.argv[-1:] == ['--help'] else "
        "print(json.dumps({'type':'turn.completed'}))\n"
    )
    executable.chmod(0o700)
    policy = tmp_path / "policy.toml"
    _policy(policy, executable, repository, adaptive=False)
    completed = _run(
        {
            "task": "Review documentation",
            "repository_root": str(repository),
            "policy_path": str(policy),
            "verification": {"kind": "command", "argv": ["/usr/bin/true"]},
        }
    )
    output = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert output["data"]["profile"] == "balanced"


def test_routing_cli_explain_and_stats_are_read_only_and_do_not_expose_concrete_model(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    executable = tmp_path / "fake-codex"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o700)
    policy = tmp_path / "policy.toml"
    _policy(policy, executable, repository)
    explain = _routing_run("explain", {"task": "Review docs", "policy_path": str(policy)})
    stats = _routing_run("stats", {"journal_root": str(tmp_path)})
    explain_output, stats_output = json.loads(explain.stdout), json.loads(stats.stdout)
    assert explain.returncode == stats.returncode == 0
    assert explain_output["data"]["selected_profile"] == "efficient"
    assert "model" not in explain_output["data"]
    assert stats_output["data"]["population_analyzed"] == 0


def test_codex_cli_emits_privacy_safe_v2_calibration_event(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    executable = tmp_path / "fake-codex"
    executable.write_text(
        "#!/usr/bin/env python3\nimport json, sys\n"
        "print('codex-cli 0.147.0') if sys.argv[1:] == ['--version'] else "
        "print('--json --strict-config --ignore-user-config --ignore-rules --model --sandbox --cd --last') if sys.argv[-1:] == ['--help'] else "
        "print(json.dumps({'type':'turn.completed','usage':{'input_tokens':7,'output_tokens':2}}))\n"
    )
    executable.chmod(0o700)
    policy = tmp_path / "policy.toml"
    _policy(policy, executable, repository)
    completed = _run({"task": "Review documentation", "repository_root": str(repository), "policy_path": str(policy), "verification": {"kind": "execution"}}, telemetry_root=tmp_path / "journal")
    records, invalid = iter_records(tmp_path / "journal")
    v2 = [record for record in records if record.get("record_type") == "codex_routing_event_v2"]
    assert completed.returncode == 0
    assert invalid == 0
    assert len(v2) == 1
    assert v2[0]["task_class"] == "routine_read_or_docs"
    assert "documentation" not in json.dumps(v2[0])
