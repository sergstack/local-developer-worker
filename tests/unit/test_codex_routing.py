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


@pytest.mark.parametrize(
    ("task", "task_class", "profile", "alias", "effort", "uncertain"),
    [
        ("Проверь README на очевидные опечатки, ничего не изменяй.", "routine_read_or_docs", "efficient", "small", "low", False),
        ("Проанализируй один локальный модуль и один связанный тест, найди возможную причину failing test, ничего не изменяй.", "bounded_change_or_debug", "balanced", "standard", "medium", False),
        ("Проанализируй этот модуль и определи, какие улучшения могут потребоваться. Ничего не изменяй.", "ambiguous", "balanced", "standard", "medium", True),
        ("Оцени влияние потенциального cross-module refactor с изменением нескольких зависимостей. Ничего не изменяй.", "cross_cutting_or_high_risk", "frontier", "large", "high", False),
    ],
)
def test_controlled_adaptive_routing_matrix(task, task_class, profile, alias, effort, uncertain):
    route = route_task(task, {}, validate_codex_policy(codex_policy()))
    assert (route.base_task_class, route.profile, route.model_alias, route.effort, route.uncertain) == (task_class, profile, alias, effort, uncertain)


@pytest.mark.parametrize("phrase", ["ничего не изменяй", "не изменяй", "не менять", "без изменений", "do not change", "don't change", "no changes", "read only", "read-only"])
def test_safety_negations_do_not_create_mutation_signal(phrase):
    route = route_task(f"Review README, {phrase}.", {}, validate_codex_policy(codex_policy()))
    assert route.base_task_class == "routine_read_or_docs"
    assert route.signal != "text:bounded_change"


@pytest.mark.parametrize("task", ["Измени README.", "Обнови локальный модуль.", "Change this module.", "Implement the requested update."])
def test_real_mutation_phrases_remain_bounded(task):
    route = route_task(task, {}, validate_codex_policy(codex_policy()))
    assert (route.base_task_class, route.profile, route.signal) == ("bounded_change_or_debug", "balanced", "text:bounded_change")


@pytest.mark.parametrize(
    "task",
    [
        "Проанализируй реализованным behavior в README.",
        "Проверь реализованную функцию.",
        "Прочитай описание изменений.",
        "Проверь историю изменений.",
        "Review the implemented behavior.",
        "Inspect the existing implementation.",
    ],
)
def test_existing_state_descriptions_do_not_create_mutation_intent(task):
    route = route_task(task, {}, validate_codex_policy(codex_policy()))
    assert route.base_task_class == "routine_read_or_docs"
    assert route.signal != "text:bounded_change"


def test_last_real_documentation_task_routes_as_read_only_analysis():
    task = (
        "Проанализируй README.md и документацию Adaptive Codex Routing в текущем репозитории. "
        "Найди противоречия между README и фактически реализованным routing/calibration behavior; "
        "устаревшие формулировки; отсутствующие пользовательские инструкции по ldw codex run, "
        "ldw routing stats и ldw routing calibrate. Ничего не изменяй. "
        "Верни только findings с evidence по файлам."
    )
    route = route_task(task, {}, validate_codex_policy(codex_policy()))
    assert (route.base_task_class, route.profile, route.signal, route.mutation_capable) == (
        "routine_read_or_docs", "efficient", "text:docs", False,
    )


@pytest.mark.parametrize("task", ["Что можно улучшить?", "Посмотри и предложи улучшения.", "Что здесь стоит изменить?", "What can be improved?", "Look at this and suggest improvements.", "What improvements may be needed?", "What is worth changing here?"])
def test_deterministic_ambiguity_signals(task):
    route = route_task(task, {}, validate_codex_policy(codex_policy()))
    assert (route.base_task_class, route.profile, route.uncertain, route.signal) == ("ambiguous", "balanced", True, "text:improvement_options")


def test_stronger_signals_take_priority_over_ambiguity():
    config = validate_codex_policy(codex_policy())
    assert route_task("Fix the bug and suggest improvements", {}, config).base_task_class == "bounded_change_or_debug"
    assert route_task("Review production security and suggest improvements", {}, config).base_task_class == "cross_cutting_or_high_risk"


def test_risk_wins_and_override_cannot_downgrade():
    config = validate_codex_policy(codex_policy())
    route = route_task("Fix production authentication", {"profile": "efficient"}, config)
    assert route.profile == "frontier"
    assert route.base_task_class == "cross_cutting_or_high_risk"
    assert route.signal == "text:security"
    assert (route.routing_disposition, route.override_requested_profile, route.override_state) == ("override_rejected", "efficient", "rejected")


def test_strong_override_preserves_base_task_class():
    route = route_task("Review README", {"profile": "frontier"}, validate_codex_policy(codex_policy()))
    assert (route.base_task_class, route.profile, route.routing_disposition, route.override_state) == ("routine_read_or_docs", "frontier", "explicit_override", "accepted")


def test_fixed_profile_rollback_and_alias_replacement_are_policy_only():
    policy = codex_policy()
    policy["codex"]["adaptive_routing"] = False
    policy["codex"]["aliases"]["standard"]["model"] = "replacement-model"
    config = validate_codex_policy(policy)
    route = route_task("production security migration", {}, config)
    assert route.profile == "balanced"
    assert route.base_task_class == "cross_cutting_or_high_risk"
    assert (route.routing_disposition, route.override_state, route.adaptive_routing) == ("fixed_profile", "none", False)
    assert config["aliases"][route.model_alias]["model"] == "replacement-model"


def test_semantic_routing_policy_does_not_affect_codex_routing():
    policy = codex_policy()
    baseline = route_task("Review README", {}, validate_codex_policy(policy))
    policy["semantic"] = {"automatic_routing": True, "enabled": True}
    isolated = route_task("Review README", {}, validate_codex_policy(policy))
    assert isolated == baseline


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
