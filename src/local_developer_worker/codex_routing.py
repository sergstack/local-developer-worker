from __future__ import annotations

import re
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROFILES = ("efficient", "balanced", "frontier")
PROFILE_RANK = {profile: rank for rank, profile in enumerate(PROFILES)}
EFFORTS = {"minimal", "low", "medium", "high", "xhigh"}
ALIAS_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
TASK_CLASSES = {
    "routine_read_or_docs": "efficient",
    "bounded_change_or_debug": "balanced",
    "cross_cutting_or_high_risk": "frontier",
    "ambiguous": "balanced",
}

HIGH_RISK_SIGNALS = (
    ("security", re.compile(r"\b(security|auth(?:entication|orization)?|permission|secret|credential|sandbox|безопасн\w*|аутентиф\w*|авторизац\w*|секрет\w*|песочниц\w*)\b", re.I)),
    ("production", re.compile(r"\b(production|deploy|migration|database|schema|payment|billing|продакш\w*|развертыв\w*|миграц\w*|схем\w*|плат[её]ж\w*|биллинг\w*)\b", re.I)),
    ("cross_cutting", re.compile(r"\b(cross[- ]cutting|architecture|multi[- ]module|repository[- ]wide|refactor|архитект\w*|сквозн\w*|рефактор\w*)\b", re.I)),
)
BOUNDED_SIGNALS = (
    ("debug", re.compile(r"\b(debug|bug|failure|failing|regression|traceback|отлад\w*|ошиб\w*|сбой\w*|регресс\w*)\b", re.I)),
)
SAFETY_NEGATIONS = (
    re.compile(r"\bничего\s+не\s+измен\w*\b", re.I),
    re.compile(r"\bне\s+измен\w*\b", re.I),
    re.compile(r"\bне\s+меня\w*\b", re.I),
    re.compile(r"\bбез\s+изменен\w*\b", re.I),
    re.compile(r"\bdo\s+not\s+change\b", re.I),
    re.compile(r"\bdon['’]t\s+change\b", re.I),
    re.compile(r"\bno\s+changes?\b", re.I),
    re.compile(r"\bread[- ]only\b", re.I),
)
MUTATION_ACTION_PATTERNS = (
    re.compile(
        r"(?:^|[.!?;:\n]\s*|[-*]\s+)(?:пожалуйста\s+)?"
        r"(?:измени(?:те)?|исправь(?:те)?|обнови(?:те)?|реализуй(?:те)?|"
        r"добавь(?:те)?|протестируй(?:те)?|пропатчь(?:те)?)\b",
        re.I,
    ),
    re.compile(
        r"(?:^|[.!?;:\n]\s*|[-*]\s+)(?:please\s+)?"
        r"(?:change|modify|update|implement|add|fix|patch|test)\b",
        re.I,
    ),
)
AMBIGUITY_SIGNALS = (
    (
        "improvement_options",
        re.compile(
            r"\b(какие\s+улучшения\s+могут\s+потребоваться|что\s+можно\s+улучшить|"
            r"посмотри\s+и\s+предложи\s+улучшения|что\s+здесь\s+стоит\s+изменить|"
            r"what\s+(?:can|could|should)\s+(?:be\s+)?improv\w*|"
            r"look\s+(?:at\s+this\s+)?and\s+suggest\s+improvements?|"
            r"what\s+(?:here\s+)?(?:is\s+worth|should)\s+chang\w*|"
            r"what\s+is\s+worth\s+chang\w*(?:\s+here)?|"
            r"(?:what|which)\s+improvements?\s+(?:may|might|could)\s+be\s+needed)\b",
            re.I,
        ),
    ),
)
ROUTINE_SIGNALS = (
    ("read", re.compile(r"\b(read|inspect|explain|summari[sz]e|review|analy[sz]e|прочит\w*|проверь\w*|объясн\w*|резюм\w*|ревью\w*|анализ\w*)\b", re.I)),
    ("docs", re.compile(r"\b(doc(?:s|umentation)?|readme|comment|typo|документ\w*|ридми\w*|комментар\w*|опечат\w*)\b", re.I)),
)

TAXONOMY_REVISION = hashlib.sha256(
    json.dumps(
        {
            "task_classes": TASK_CLASSES,
            "high_risk": [(code, pattern.pattern) for code, pattern in HIGH_RISK_SIGNALS],
            "bounded": [(code, pattern.pattern) for code, pattern in BOUNDED_SIGNALS],
            "safety_negations": [pattern.pattern for pattern in SAFETY_NEGATIONS],
            "mutation_actions": [pattern.pattern for pattern in MUTATION_ACTION_PATTERNS],
            "ambiguity": [(code, pattern.pattern) for code, pattern in AMBIGUITY_SIGNALS],
            "routine": [(code, pattern.pattern) for code, pattern in ROUTINE_SIGNALS],
        },
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


class CodexConfigError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code


@dataclass(frozen=True)
class Route:
    profile: str
    model_alias: str
    effort: str
    signal: str
    uncertain: bool
    mutation_capable: bool
    deterministic_risk_floor: str
    policy_revision: str
    base_task_class: str = "ambiguous"
    routing_disposition: str = "adaptive"
    override_requested_profile: str | None = None
    override_state: str = "none"
    adaptive_routing: bool = True


@dataclass(frozen=True)
class Classification:
    task_class: str
    profile: str
    signal: str
    uncertain: bool
    mutation_capable: bool


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise CodexConfigError("invalid_codex_config", f"{field} must be a non-empty string")
    return value


def _profile(value: Any, field: str) -> str:
    profile = _string(value, field)
    if profile not in PROFILE_RANK:
        raise CodexConfigError("invalid_codex_config", f"{field} must be a routing profile")
    return profile


def validate_codex_policy(policy: dict[str, Any]) -> dict[str, Any]:
    raw = policy.get("codex")
    if not isinstance(raw, dict):
        raise CodexConfigError("codex_disabled", "[codex] policy is absent")
    if raw.get("enabled") is not True:
        raise CodexConfigError("codex_disabled")
    for flag in ("adaptive_routing", "allow_profile_downgrade", "allow_write", "allow_network"):
        if not isinstance(raw.get(flag, False), bool):
            raise CodexConfigError("invalid_codex_config", f"{flag} must be boolean")
    if raw.get("allow_network") is not True or policy.get("network_access") is not True:
        raise CodexConfigError("codex_network_disabled")
    if any(policy.get(field) is True for field in ("automatic_commit", "automatic_merge", "production_deploy")):
        raise CodexConfigError("codex_authority_conflict")
    default_profile = _profile(raw.get("default_profile"), "default_profile")
    risk_floor = _profile(raw.get("risk_floor", "efficient"), "risk_floor")
    maximum_profile = _profile(raw.get("maximum_profile", "frontier"), "maximum_profile")
    if PROFILE_RANK[risk_floor] > PROFILE_RANK[maximum_profile]:
        raise CodexConfigError("invalid_codex_config", "risk_floor exceeds maximum_profile")

    profiles = raw.get("profiles")
    aliases = raw.get("aliases")
    if not isinstance(profiles, dict) or set(profiles) != set(PROFILES) or not isinstance(aliases, dict) or not aliases:
        raise CodexConfigError("invalid_codex_config", "all profiles and aliases are required")
    normalized_profiles: dict[str, dict[str, str]] = {}
    for profile in PROFILES:
        row = profiles.get(profile)
        if not isinstance(row, dict):
            raise CodexConfigError("invalid_codex_config", f"invalid profile {profile}")
        alias = _string(row.get("alias"), f"profiles.{profile}.alias")
        effort = _string(row.get("effort"), f"profiles.{profile}.effort")
        if effort not in EFFORTS or alias not in aliases:
            raise CodexConfigError("invalid_codex_config", f"unresolved profile {profile}")
        normalized_profiles[profile] = {"alias": alias, "effort": effort}

    normalized_aliases: dict[str, dict[str, Any]] = {}
    for name, row in aliases.items():
        if not isinstance(name, str) or ALIAS_PATTERN.fullmatch(name) is None or not isinstance(row, dict):
            raise CodexConfigError("invalid_codex_config", "invalid alias")
        model = _string(row.get("model"), f"aliases.{name}.model")
        supported = row.get("supported_efforts")
        fallbacks = row.get("fallback_aliases", [])
        if (
            not isinstance(supported, list) or not supported
            or any(not isinstance(effort, str) or effort not in EFFORTS for effort in supported)
            or not isinstance(fallbacks, list)
            or any(not isinstance(item, str) for item in fallbacks)
        ):
            raise CodexConfigError("invalid_codex_config", f"invalid alias capabilities for {name}")
        if len(supported) != len(set(supported)) or len(fallbacks) != len(set(fallbacks)):
            raise CodexConfigError("invalid_codex_config", f"duplicate alias capabilities for {name}")
        normalized_aliases[name] = {
            "model": model,
            "supported_efforts": tuple(supported),
            "fallback_aliases": tuple(fallbacks),
        }
    for name, row in normalized_aliases.items():
        if any(item not in normalized_aliases or item == name for item in row["fallback_aliases"]):
            raise CodexConfigError("invalid_codex_config", f"invalid fallback for {name}")
    for profile, row in normalized_profiles.items():
        if row["effort"] not in normalized_aliases[row["alias"]]["supported_efforts"]:
            raise CodexConfigError("invalid_codex_config", f"unsupported effort for {profile}")
        def visit(alias: str, active: set[str], visited: set[str]) -> None:
            if alias in active:
                raise CodexConfigError("invalid_codex_config", "alias fallback cycle")
            if alias in visited:
                return
            active.add(alias)
            if row["effort"] not in normalized_aliases[alias]["supported_efforts"]:
                raise CodexConfigError("invalid_codex_config", f"fallback effort mismatch for {profile}")
            for target in normalized_aliases[alias]["fallback_aliases"]:
                visit(target, active, visited)
            active.remove(alias)
            visited.add(alias)
        visit(row["alias"], set(), set())

    escalation = raw.get("escalation", {})
    if not isinstance(escalation, dict):
        raise CodexConfigError("invalid_codex_config", "escalation must be a table")
    normalized_escalation: dict[str, str] = {}
    for source, target in escalation.items():
        source_profile, target_profile = _profile(source, "escalation source"), _profile(target, "escalation target")
        if PROFILE_RANK[target_profile] <= PROFILE_RANK[source_profile]:
            raise CodexConfigError("invalid_codex_config", "escalation must increase profile")
        normalized_escalation[source_profile] = target_profile
    cursor_seen: set[str] = set()
    cursor = "efficient"
    while cursor in normalized_escalation:
        if cursor in cursor_seen:
            raise CodexConfigError("invalid_codex_config", "escalation cycle")
        cursor_seen.add(cursor)
        cursor = normalized_escalation[cursor]

    executable = Path(_string(raw.get("executable"), "executable"))
    allowed_executables = raw.get("allowed_executables")
    verification_executables = raw.get("verification_executables", [])
    verification_commands = raw.get("verification_commands", [])
    environment_allowlist = raw.get("environment_allowlist", ["HOME", "PATH", "CODEX_HOME"])
    supported_versions = raw.get("supported_cli_versions", [])
    if not executable.is_absolute() or not isinstance(allowed_executables, list) or not allowed_executables:
        raise CodexConfigError("invalid_codex_config", "absolute executable allowlist required")
    if any(not isinstance(item, str) or not Path(item).is_absolute() for item in allowed_executables):
        raise CodexConfigError("invalid_codex_config", "allowed executables must be absolute")
    if not isinstance(verification_executables, list) or any(not isinstance(item, str) or not Path(item).is_absolute() for item in verification_executables):
        raise CodexConfigError("invalid_codex_config", "verification executables must be absolute")
    if not isinstance(verification_commands, list) or any(
        not isinstance(command, list)
        or not command
        or any(not isinstance(item, str) or not item for item in command)
        for command in verification_commands
    ):
        raise CodexConfigError("invalid_codex_config", "verification commands must use allowed executables")
    if len({tuple(command) for command in verification_commands}) != len(verification_commands) or any(
        command[0] not in verification_executables for command in verification_commands
    ):
        raise CodexConfigError("invalid_codex_config", "verification commands must be unique and allowed")
    if not isinstance(environment_allowlist, list) or any(not isinstance(item, str) or not item for item in environment_allowlist):
        raise CodexConfigError("invalid_codex_config", "invalid environment allowlist")
    if not isinstance(supported_versions, list) or not supported_versions or any(not isinstance(item, str) or not item for item in supported_versions):
        raise CodexConfigError("invalid_codex_config", "supported CLI versions required")
    sandbox = _string(raw.get("sandbox", "read-only"), "sandbox")
    approval = _string(raw.get("approval_policy", "never"), "approval_policy")
    if sandbox not in {"read-only", "workspace-write"} or approval != "never":
        raise CodexConfigError("invalid_codex_config", "unsupported sandbox or approval policy")
    if sandbox == "workspace-write" and raw.get("allow_write") is not True:
        raise CodexConfigError("codex_write_disabled")
    limits = (
        raw.get("max_escalations", 0),
        raw.get("timeout_seconds", 900),
        raw.get("verification_timeout_seconds", 300),
        raw.get("max_output_bytes", 5_000_000),
        raw.get("max_task_bytes", 100_000),
    )
    if any(not isinstance(value, int) or isinstance(value, bool) for value in limits):
        raise CodexConfigError("invalid_codex_config", "limits must be integers")
    max_escalations, timeout_seconds, verification_timeout_seconds, max_output_bytes, max_task_bytes = limits
    if not 0 <= max_escalations <= 5 or min(timeout_seconds, verification_timeout_seconds, max_output_bytes, max_task_bytes) <= 0:
        raise CodexConfigError("invalid_codex_config", "limits out of range")
    retriable = raw.get("retriable_error_codes", [])
    if not isinstance(retriable, list) or any(not isinstance(item, str) or not item for item in retriable):
        raise CodexConfigError("invalid_codex_config", "invalid retriable errors")
    calibration = raw.get("calibration", {})
    if not isinstance(calibration, dict):
        raise CodexConfigError("invalid_codex_config", "calibration must be a table")
    calibration_defaults = {
        "enabled": False,
        "min_samples": 20,
        "strong_sample": 50,
        "max_age_days": 90,
        "under_routing_escalation_rate": 0.35,
        "under_routing_first_pass_rate": 0.8,
        "over_routing_first_pass_rate": 0.95,
    }
    unknown_calibration = set(calibration) - set(calibration_defaults)
    if unknown_calibration:
        raise CodexConfigError("invalid_codex_config", "unknown calibration field")
    calibration_values = {name: calibration.get(name, default) for name, default in calibration_defaults.items()}
    if not isinstance(calibration_values["enabled"], bool) or any(
        not isinstance(calibration_values[name], int) or isinstance(calibration_values[name], bool) or calibration_values[name] < 1
        for name in ("min_samples", "strong_sample", "max_age_days")
    ):
        raise CodexConfigError("invalid_codex_config", "invalid calibration sample configuration")
    if calibration_values["strong_sample"] < calibration_values["min_samples"] or any(
        not isinstance(calibration_values[name], (int, float)) or isinstance(calibration_values[name], bool) or not 0 <= calibration_values[name] <= 1
        for name in ("under_routing_escalation_rate", "under_routing_first_pass_rate", "over_routing_first_pass_rate")
    ):
        raise CodexConfigError("invalid_codex_config", "invalid calibration threshold configuration")
    routing_revision = hashlib.sha256(json.dumps({
        "adaptive_routing": raw.get("adaptive_routing", False), "default_profile": default_profile,
        "risk_floor": risk_floor, "maximum_profile": maximum_profile, "escalation": normalized_escalation,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    alias_revision = hashlib.sha256(json.dumps({"profiles": normalized_profiles, "aliases": normalized_aliases}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=list).encode("utf-8")).hexdigest()
    return {
        "adaptive_routing": raw.get("adaptive_routing", False),
        "allow_profile_downgrade": raw.get("allow_profile_downgrade", False),
        "allow_write": raw.get("allow_write", False),
        "default_profile": default_profile,
        "risk_floor": risk_floor,
        "maximum_profile": maximum_profile,
        "profiles": normalized_profiles,
        "aliases": normalized_aliases,
        "escalation": normalized_escalation,
        "executable": str(executable),
        "allowed_executables": tuple(allowed_executables),
        "verification_executables": tuple(verification_executables),
        "verification_commands": tuple(tuple(command) for command in verification_commands),
        "environment_allowlist": tuple(environment_allowlist),
        "supported_cli_versions": tuple(supported_versions),
        "sandbox": sandbox,
        "approval_policy": approval,
        "max_escalations": max_escalations,
        "timeout_seconds": timeout_seconds,
        "verification_timeout_seconds": verification_timeout_seconds,
        "max_output_bytes": max_output_bytes,
        "max_task_bytes": max_task_bytes,
        "retriable_error_codes": frozenset(retriable),
        "policy_revision": hashlib.sha256(
            json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest(),
        "routing_revision": routing_revision,
        "alias_revision": alias_revision,
        "taxonomy_revision": TAXONOMY_REVISION,
    }


def _apply_floor_and_ceiling(profile: str, floor: str, maximum: str) -> str:
    rank = max(PROFILE_RANK[profile], PROFILE_RANK[floor])
    if rank > PROFILE_RANK[maximum]:
        raise CodexConfigError("route_exceeds_maximum_profile")
    return PROFILES[rank]


def _without_patterns(text: str, patterns: tuple[re.Pattern[str], ...]) -> str:
    for pattern in patterns:
        text = pattern.sub(" ", text)
    return text


def _has_mutation_action(task: str) -> bool:
    normalized = _without_patterns(task, SAFETY_NEGATIONS).strip()
    return any(pattern.search(normalized) for pattern in MUTATION_ACTION_PATTERNS)


def classify_task(task: str, task_class: str | None = None) -> Classification:
    if task_class is not None:
        if task_class not in TASK_CLASSES:
            raise CodexConfigError("invalid_codex_input", "unknown task_class")
        return Classification(
            task_class,
            TASK_CLASSES[task_class],
            f"structured:{task_class}",
            task_class == "ambiguous",
            task_class != "routine_read_or_docs",
        )

    for code, pattern in HIGH_RISK_SIGNALS:
        if pattern.search(task):
            return Classification("cross_cutting_or_high_risk", "frontier", f"text:{code}", False, True)

    for code, pattern in BOUNDED_SIGNALS:
        if pattern.search(task):
            return Classification("bounded_change_or_debug", "balanced", f"text:{code}", False, True)

    ambiguity_patterns = tuple(pattern for _, pattern in AMBIGUITY_SIGNALS)
    mutation_text = _without_patterns(task, ambiguity_patterns)
    if _has_mutation_action(mutation_text):
        return Classification("bounded_change_or_debug", "balanced", "text:bounded_change", False, True)

    for code, pattern in AMBIGUITY_SIGNALS:
        if pattern.search(task):
            return Classification("ambiguous", "balanced", f"text:{code}", True, True)

    for code, pattern in ROUTINE_SIGNALS:
        if pattern.search(task):
            return Classification("routine_read_or_docs", "efficient", f"text:{code}", False, False)
    return Classification("ambiguous", "balanced", "default:ambiguous", True, True)


def route_task(task: str, payload: dict[str, Any], config: dict[str, Any]) -> Route:
    if not isinstance(task, str) or not task.strip():
        raise CodexConfigError("invalid_codex_input", "task must be non-empty")
    classification = classify_task(task, payload.get("task_class"))
    profile = classification.profile if config["adaptive_routing"] else config["default_profile"]
    disposition = "adaptive" if config["adaptive_routing"] else "fixed_profile"
    override_state = "none"
    override = payload.get("profile")
    deterministic_floor = PROFILES[max(PROFILE_RANK[profile], PROFILE_RANK[config["risk_floor"]])]
    profile = deterministic_floor
    if override is not None:
        override = _profile(override, "profile override")
        if PROFILE_RANK[override] < PROFILE_RANK[deterministic_floor] and not config["allow_profile_downgrade"]:
            disposition, override_state = "override_rejected", "rejected"
        else:
            profile, disposition, override_state = override, "explicit_override", "accepted"
    profile = _apply_floor_and_ceiling(
        profile,
        "efficient" if config["allow_profile_downgrade"] and override is not None else deterministic_floor,
        config["maximum_profile"],
    )
    profile_row = config["profiles"][profile]
    return Route(
        profile,
        profile_row["alias"],
        profile_row["effort"],
        classification.signal,
        classification.uncertain,
        classification.mutation_capable,
        deterministic_floor,
        config["policy_revision"],
        classification.task_class,
        disposition,
        override,
        override_state,
        config["adaptive_routing"],
    )


def route_for_profile(profile: str, config: dict[str, Any], signal: str = "escalation") -> Route:
    profile = _apply_floor_and_ceiling(_profile(profile, "profile"), config["risk_floor"], config["maximum_profile"])
    row = config["profiles"][profile]
    return Route(profile, row["alias"], row["effort"], signal, False, True, profile, config["policy_revision"], "ambiguous", "escalation", None, "none", config["adaptive_routing"])
