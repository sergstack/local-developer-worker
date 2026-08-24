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
    assert output["data"]["execution_attempted"] is True
    assert output["data"]["model_execution_completed"] is True
    assert output["data"]["calibration_eligible"] is True
    assert output["data"]["non_cached_input_tokens"] is None
    assert output["data"]["provider_total_tokens"] == 9
    assert output["data"]["reasoning_in_output_status"] == "unknown"
    assert "ephemeral-test-id" not in completed.stdout


def test_cli_allows_read_only_execution_without_git_and_marks_missing_git_evidence(tmp_path):
    repository = tmp_path / "not-a-git-repository"
    repository.mkdir()
    executable = tmp_path / "fake-codex"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "if sys.argv[1:] == ['--version']:\n print('codex-cli 0.147.0')\n"
        "elif sys.argv[-1:] == ['--help']:\n print('--json --strict-config --ignore-user-config --ignore-rules --model --sandbox --cd --last')\n"
        "else:\n print(json.dumps({'type':'turn.completed'}))\n"
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
    assert completed.returncode == 0
    assert output["status"] == "success"
    assert output["data"]["model_execution_completed"] is True
    assert output["warnings"] == [{"code": "git_evidence_not_available"}]


def test_cli_flushes_one_terminal_result_after_a_delayed_codex_execution(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    executable = tmp_path / "fake-codex"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys, time\n"
        "if sys.argv[1:] == ['--version']:\n"
        " print('codex-cli 0.147.0')\n"
        "elif sys.argv[-1:] == ['--help']:\n"
        " print('--json --strict-config --ignore-user-config --ignore-rules --model --sandbox --cd --last')\n"
        "else:\n"
        " time.sleep(0.05)\n"
        " print(json.dumps({'type':'turn.completed','usage':{'input_tokens':7,'output_tokens':2}}))\n"
    )
    executable.chmod(0o700)
    policy = tmp_path / "policy.toml"
    _policy(policy, executable, repository)
    journal = tmp_path / "journal"

    completed = _run(
        {"task": "Review documentation", "repository_root": str(repository), "policy_path": str(policy), "verification": {"kind": "execution"}},
        telemetry_root=journal,
    )

    assert completed.returncode == 0
    assert len(completed.stdout.splitlines()) == 1
    output = json.loads(completed.stdout)
    records, invalid = iter_records(journal)
    event = next(record for record in records if record.get("record_type") == "codex_routing_event_v2")
    assert output["data"]["terminal_status"] == "pass"
    assert output["data"]["execution_id"] == event["execution_id"]
    assert invalid == 0


def test_routing_value_renders_existing_run_without_writing_telemetry(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    executable = tmp_path / "fake-codex"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "if sys.argv[1:] == ['--version']:\n print('codex-cli 0.147.0')\n"
        "elif sys.argv[-1:] == ['--help']:\n print('--json --strict-config --ignore-user-config --ignore-rules --model --sandbox --cd --last')\n"
        "else:\n print(json.dumps({'type':'turn.completed','usage':{'input_tokens':7,'output_tokens':2}}))\n"
    )
    executable.chmod(0o700)
    policy = tmp_path / "policy.toml"
    _policy(policy, executable, repository)
    journal = tmp_path / "journal"
    run = _run({"task": "Review documentation", "repository_root": str(repository), "policy_path": str(policy), "verification": {"kind": "execution"}}, telemetry_root=journal)
    records_before, invalid_before = iter_records(journal)
    rendered = _routing_run("value", {"codex_result": json.loads(run.stdout), "journal_root": str(journal)})
    records_after, invalid_after = iter_records(journal)

    output = json.loads(rendered.stdout)
    assert run.returncode == rendered.returncode == 0
    assert invalid_before == invalid_after == 0
    assert records_after == records_before
    assert output["data"]["observed"]["latency"]["status"] == "observed"
    assert output["data"]["comparison"]["status"] == "not_available"
    validate(output["data"], json.loads((ROOT / "schemas/routing_value_data.schema.json").read_text()))


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
    assert stats_output["data"]["retention_days"] == 90


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
    assert v2[0]["base_task_class"] == "routine_read_or_docs"
    assert v2[0]["schema_version"] == "2.4.0"
    assert v2[0]["execution_id"].startswith("EXEC-")
    assert v2[0]["calibration_eligible"] is True
    assert v2[0]["routing_disposition"] == "adaptive"
    assert v2[0]["override_state"] == "none"
    assert "documentation" not in json.dumps(v2[0])


def test_identical_invocations_keep_deterministic_run_id_but_get_distinct_execution_ids(tmp_path):
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
    journal = tmp_path / "journal"
    payload = {"task": "Review documentation", "repository_root": str(repository), "policy_path": str(policy), "verification": {"kind": "execution"}}
    first, second = _run(payload, telemetry_root=journal), _run(payload, telemetry_root=journal)
    first_output, second_output = json.loads(first.stdout), json.loads(second.stdout)
    records, invalid = iter_records(journal)
    events = [record for record in records if record.get("record_type") == "codex_routing_event_v2"]
    stats = _routing_run("stats", {"journal_root": str(journal)})
    assert first.returncode == second.returncode == 0
    assert first_output["run_id"] == second_output["run_id"]
    assert first_output["data"]["execution_id"] != second_output["data"]["execution_id"]
    assert {event["execution_id"] for event in events} == {first_output["data"]["execution_id"], second_output["data"]["execution_id"]}
    assert invalid == 0
    assert json.loads(stats.stdout)["data"]["population_analyzed"] == 2


def test_blocked_preflight_and_completed_run_produce_one_calibration_sample(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    executable = tmp_path / "fake-codex"
    executable.write_text(
        "#!/usr/bin/env python3\nimport json, sys\n"
        "print('codex-cli 0.147.0') if sys.argv[1:] == ['--version'] else "
        "print('--json --strict-config --ignore-user-config --ignore-rules --model --sandbox --cd --last') if sys.argv[-1:] == ['--help'] else "
        "print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'cached_input_tokens':4,'output_tokens':2,'reasoning_output_tokens':1}}))\n"
    )
    executable.chmod(0o700)
    policy = tmp_path / "policy.toml"
    _policy(policy, executable, repository)
    journal = tmp_path / "journal"
    blocked = _run({"task": "Change this module", "repository_root": str(repository), "policy_path": str(policy), "verification": {"kind": "command", "argv": ["/bin/false"]}}, telemetry_root=journal)
    completed = _run({"task": "Review documentation", "repository_root": str(repository), "policy_path": str(policy), "verification": {"kind": "execution"}}, telemetry_root=journal)
    stats = _routing_run("stats", {"journal_root": str(journal)})
    blocked_output, completed_output, stats_output = map(lambda row: json.loads(row.stdout), (blocked, completed, stats))
    assert blocked_output["data"]["calibration_eligible"] is False
    assert blocked_output["data"]["execution_attempted"] is False
    assert completed_output["data"]["calibration_eligible"] is True
    assert completed_output["data"]["provider_total_tokens"] == 12
    assert completed_output["data"]["non_cached_input_tokens"] == 6
    assert stats_output["data"]["operational_records"] == 2
    assert stats_output["data"]["excluded_ineligible_records"] == 1
    assert stats_output["data"]["population_analyzed"] == 1


def test_codex_cli_telemetry_preserves_base_class_across_override_and_fixed_modes(tmp_path):
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
    completed = _run({"task": "Review README", "profile": "frontier", "repository_root": str(repository), "policy_path": str(policy), "verification": {"kind": "execution"}}, telemetry_root=tmp_path / "journal")
    records, invalid = iter_records(tmp_path / "journal")
    event = [record for record in records if record.get("record_type") == "codex_routing_event_v2"][0]
    assert completed.returncode == 0
    assert invalid == 0
    assert event["base_task_class"] == "routine_read_or_docs"
    assert event["routing_signal"] == "text:read"
    assert (event["routing_disposition"], event["override_requested_profile"], event["override_state"]) == ("explicit_override", "frontier", "accepted")

    _policy(policy, executable, repository, adaptive=False)
    fixed = _run({"task": "Review production security", "repository_root": str(repository), "policy_path": str(policy), "verification": {"kind": "command", "argv": ["/usr/bin/true"]}}, telemetry_root=tmp_path / "fixed-journal")
    fixed_records, fixed_invalid = iter_records(tmp_path / "fixed-journal")
    fixed_event = [record for record in fixed_records if record.get("record_type") == "codex_routing_event_v2"][0]
    assert fixed.returncode == 0
    assert fixed_invalid == 0
    assert fixed_event["base_task_class"] == "cross_cutting_or_high_risk"
    assert (fixed_event["routing_disposition"], fixed_event["override_state"], fixed_event["adaptive_routing"]) == ("fixed_profile", "none", False)

    _policy(policy, executable, repository)
    rejected = _run({"task": "Review production security", "profile": "efficient", "repository_root": str(repository), "policy_path": str(policy), "verification": {"kind": "command", "argv": ["/usr/bin/true"]}}, telemetry_root=tmp_path / "rejected-journal")
    rejected_records, rejected_invalid = iter_records(tmp_path / "rejected-journal")
    rejected_event = [record for record in rejected_records if record.get("record_type") == "codex_routing_event_v2"][0]
    assert rejected.returncode == 0
    assert rejected_invalid == 0
    assert rejected_event["base_task_class"] == "cross_cutting_or_high_risk"
    assert rejected_event["routing_signal"] == "text:security"
    assert (rejected_event["routing_disposition"], rejected_event["override_requested_profile"], rejected_event["override_state"]) == ("override_rejected", "efficient", "rejected")
