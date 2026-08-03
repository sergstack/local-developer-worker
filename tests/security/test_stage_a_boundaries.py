from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

from local_developer_worker.tools import git_facts


ROOT = Path(__file__).parents[2]


def test_gate_default_policy_denies_network_mutation_and_deployment():
    with (ROOT / "policy.toml").open("rb") as handle:
        policy = tomllib.load(handle)

    assert policy["network_access"] is False
    assert policy["automatic_edit"] is False
    assert policy["automatic_commit"] is False
    assert policy["automatic_merge"] is False
    assert policy["production_deploy"] is False
    assert policy["semantic"]["enabled"] is False


def test_gate_git_facts_can_only_reach_read_only_git_subcommands(tmp_path, monkeypatch):
    observed: list[tuple[str, ...]] = []

    def fake_run(argv, **kwargs):
        command = tuple(argv[3:])
        observed.append(command)
        stdout = "main\n" if command == ("rev-parse", "--abbrev-ref", "HEAD") else ""
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr("local_developer_worker.tools.subprocess.run", fake_run)
    output = git_facts({"repository_root": str(tmp_path)})

    assert output["status"] == "success"
    assert observed == [
        ("rev-parse", "--abbrev-ref", "HEAD"),
        ("status", "--porcelain=v1", "-z"),
        ("diff", "--numstat", "HEAD"),
    ]
    assert not ({"add", "commit", "checkout", "clean", "merge", "push", "reset", "restore", "switch"} & {command[0] for command in observed})
