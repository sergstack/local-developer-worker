from __future__ import annotations

import json
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
    assert policy["automatic"]["semantic_log_clustering"] is False
    assert policy["semantic"]["enabled"] is False
    assert policy["semantic"]["code_artifact"] == "disabled"


def test_gate_sa14_records_the_narrow_semantic_clustering_exception():
    registry = json.loads((ROOT / "docs" / "gate_registry.json").read_text())
    sa14 = next(item for item in registry["items"] if item["id"] == "SA-14")

    assert sa14["guarantee"] == (
        "denies network, edit, commit, merge, deploy by default; semantic authority is default-off "
        "but may be narrowly enabled for the gated bounded clustering task under "
        "[automatic].semantic_log_clustering, never for code_artifact"
    )
    assert sa14["enforcement"] == (
        "The shipped policy denies network and mutation capabilities, keeps semantic clustering "
        "default-off, and requires both [semantic].enabled and "
        "[automatic].semantic_log_clustering before dispatch; code_artifact remains disabled."
    )


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
