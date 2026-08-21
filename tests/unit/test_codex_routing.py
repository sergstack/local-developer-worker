from __future__ import annotations

import copy
from pathlib import Path

import pytest

from local_developer_worker.codex_routing import CodexConfigError, route_task, validate_codex_policy


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


@pytest.mark.parametrize(
    ("payload", "task", "profile", "mutation", "uncertain"),
    [
        ({"task_class": "routine_read_or_docs"}, "anything", "efficient", False, False),
        ({"task_class": "bounded_change_or_debug"}, "anything", "balanced", True, False),
        ({"task_class": "cross_cutting_or_high_risk"}, "anything", "frontier", True, False),
        ({"task_class": "ambiguous"}, "anything", "balanced", True, True),
        ({}, "Review the README", "efficient", False, False),
        ({}, "Fix the failing unit test", "balanced", True, False),
        ({}, "Change production authentication", "frontier", True, False),
        ({}, "Do the thing", "balanced", True, True),
        ({}, "Проверь документацию", "efficient", False, False),
        ({}, "Исправь ошибку в тесте", "balanced", True, False),
        ({}, "Миграция продакшн авторизации", "frontier", True, False),
    ],
)
def test_every_routing_class(payload, task, profile, mutation, uncertain):
    route = route_task(task, payload, validate_codex_policy(codex_policy()))
    assert (route.profile, route.mutation_capable, route.uncertain) == (profile, mutation, uncertain)


def test_risk_wins_and_override_cannot_downgrade():
    config = validate_codex_policy(codex_policy())
    route = route_task("Fix production authentication", {"profile": "efficient"}, config)
    assert route.profile == "frontier"
    assert route.signal.endswith("override_rejected")


def test_fixed_profile_rollback_and_alias_replacement_are_policy_only():
    policy = codex_policy()
    policy["codex"]["adaptive_routing"] = False
    policy["codex"]["aliases"]["standard"]["model"] = "replacement-model"
    config = validate_codex_policy(policy)
    route = route_task("production security migration", {}, config)
    assert route.profile == "balanced"
    assert config["aliases"][route.model_alias]["model"] == "replacement-model"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row.update(enabled=False),
        lambda row: row.update(allow_network=False),
        lambda row: row.update(approval_policy="on-request"),
        lambda row: row.update(sandbox="workspace-write", allow_write=False),
        lambda row: row["profiles"]["balanced"].update(effort="high"),
        lambda row: row["escalation"].update(frontier="efficient"),
        lambda row: row.update(executable="relative/codex"),
    ],
)
def test_invalid_or_disabled_configuration_fails_closed(mutation):
    policy = copy.deepcopy(codex_policy())
    mutation(policy["codex"])
    with pytest.raises(CodexConfigError):
        validate_codex_policy(policy)


def test_fallback_cycle_is_rejected_at_configuration_time():
    policy = codex_policy()
    policy["codex"]["aliases"]["small"]["fallback_aliases"] = ["backup"]
    policy["codex"]["aliases"]["backup"] = {
        "model": "backup-model",
        "supported_efforts": ["low"],
        "fallback_aliases": ["small"],
    }
    with pytest.raises(CodexConfigError):
        validate_codex_policy(policy)


def test_invalid_calibration_configuration_fails_closed():
    policy = codex_policy()
    policy["codex"]["calibration"] = {"enabled": True, "min_samples": 50, "strong_sample": 20}
    with pytest.raises(CodexConfigError):
        validate_codex_policy(policy)
