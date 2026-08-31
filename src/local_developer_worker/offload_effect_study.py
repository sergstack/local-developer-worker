"""Analyze sanitized matched offload evidence without executing any route.

The analyzer accepts only opaque match identifiers and aggregate measurements.
It does not invoke a model, read a telemetry journal, mutate policy, or decide
whether a local route may be promoted.  Its strongest outcome is a review
packet for AI-OS.
"""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

from .contracts import canonical_json, result, stable_hash


CONTRACT_VERSION = "1.0.0"
MATCHED_CAPTURE_VERSION = "1.1.0"
MIN_LIVE_PAIRS = 3
ROOT_FIELDS = {"contract_version", "study_id", "mode", "evidence_status", "pairs"}
PAIR_FIELDS = {"match_id", "task_class", "acceptance_source", "gold_accepted", "control", "candidate"}
ARM_FIELDS = {
    "route", "terminal_status", "verification_status", "accepted", "latency_ms",
    "provider_input_tokens", "provider_output_tokens", "context_bytes", "local_compute_ms",
    "fallback_count", "escalation_count", "failure_code", "policy_revision",
}
ROUTES = {"local", "deterministic", "frontier", "blocked"}
TERMINAL_STATUSES = {"candidate_ready", "pass", "failed", "blocked"}
VERIFICATION_STATUSES = {"passed", "failed", "uncertain", "not_run", "schema_valid", "observed_success"}
ACCEPTANCE_SOURCES = {"gold", "verifier", "none"}
MATCHED_ROOT_FIELDS = ROOT_FIELDS | {"sampling_contract_id"}
MATCHED_PAIR_FIELDS = PAIR_FIELDS | {
    "environment_revision", "budget", "timeout_ms", "verifier_id",
    "acceptance_contract_id", "arm_order",
}
MATCHED_ARM_FIELDS = {
    "route", "profile", "terminal_status", "verification_status", "accepted",
    "wall_clock_ms", "provider_input_tokens", "provider_output_tokens",
    "provider_cost_usd", "local_compute_ms", "initial_context_bytes",
    "cumulative_context_bytes", "context_expansion_count", "expansion_added_bytes",
    "compaction_count", "reread_after_compaction_count", "agent_tool_calls",
    "ldw_tool_calls", "correction_iterations", "preliminary_attempt_count",
    "fallback_count", "escalation_count", "failure_codes", "policy_revision",
}
MATCHED_ROUTES = ROUTES | {"direct"}
ARM_ORDERS = {"control_first", "candidate_first"}
REASON_CODES = {
    "DIRECT_PATH_SUFFICIENT", "EXPAND_MISSING_DEPENDENCY", "EXPAND_MISSING_TEST_CONTEXT",
    "EXPAND_OTHER_BOUNDED_REASON", "REREAD_AFTER_COMPACTION", "ROUTE_UNDERSHOOT",
    "ROUTE_OVERSHOOT", "LOCAL_VERIFIER_REJECT", "LOCAL_RUNTIME_UNAVAILABLE",
    "FRONTIER_FALLBACK", "EXACT_SESSION_ESCALATION", "REPEATED_TOOL_READ",
    "STALE_CONTEXT_OR_EVIDENCE_REFRESH", "OTHER_OBSERVED",
}
MATCHED_METRICS = (
    "wall_clock_ms", "provider_total_tokens", "provider_cost_usd", "local_compute_ms",
    "initial_context_bytes", "cumulative_context_bytes", "context_expansion_count",
    "expansion_added_bytes", "compaction_count", "reread_after_compaction_count",
    "agent_tool_calls", "ldw_tool_calls", "total_tool_calls", "correction_iterations",
    "preliminary_attempt_count", "fallback_count", "escalation_count",
)
REQUIRED_END_TO_END_FIELDS = {
    "wall_clock_ms", "agent_tool_calls", "ldw_tool_calls", "correction_iterations",
    "preliminary_attempt_count", "fallback_count", "escalation_count",
}
MATCHED_COUNT_FIELDS = MATCHED_ARM_FIELDS - {
    "route", "profile", "terminal_status", "verification_status", "accepted", "provider_cost_usd",
    "failure_codes", "policy_revision",
}


def _exact(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"invalid_{label}")
    return value


def _opaque_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise ValueError(f"invalid_{label}")
    if not all(char.isascii() and (char.isupper() or char.isdigit() or char in "_-") for char in value):
        raise ValueError(f"invalid_{label}")
    return value


def _task_class(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise ValueError("invalid_task_class")
    if not value[0].islower() or not all(char.isascii() and (char.islower() or char.isdigit() or char == "_") for char in value):
        raise ValueError("invalid_task_class")
    return value


def _non_negative(value: Any, label: str, *, nullable: bool = True) -> int | None:
    if value is None and nullable:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"invalid_{label}")
    return value


def _validate_arm(value: Any) -> dict[str, Any]:
    arm = _exact(value, ARM_FIELDS, "offload_study_arm")
    if arm["route"] not in ROUTES or arm["terminal_status"] not in TERMINAL_STATUSES:
        raise ValueError("invalid_offload_study_arm")
    if arm["verification_status"] not in VERIFICATION_STATUSES:
        raise ValueError("invalid_offload_study_arm")
    if arm["accepted"] is not None and not isinstance(arm["accepted"], bool):
        raise ValueError("invalid_offload_study_arm")
    for field in {"latency_ms", "provider_input_tokens", "provider_output_tokens", "context_bytes", "local_compute_ms"}:
        _non_negative(arm[field], field)
    for field in {"fallback_count", "escalation_count"}:
        _non_negative(arm[field], field, nullable=False)
    if arm["failure_code"] is not None:
        _opaque_identifier(arm["failure_code"], "failure_code")
    if not isinstance(arm["policy_revision"], str) or len(arm["policy_revision"]) != 64 or any(char not in "0123456789abcdef" for char in arm["policy_revision"]):
        raise ValueError("invalid_policy_revision")
    return arm


def _nullable_non_negative(value: Any, label: str) -> int | float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ValueError(f"invalid_{label}")
    return value


def _validate_matched_arm(value: Any) -> dict[str, Any]:
    arm = _exact(value, MATCHED_ARM_FIELDS, "matched_study_arm")
    if arm["route"] not in MATCHED_ROUTES or arm["terminal_status"] not in TERMINAL_STATUSES:
        raise ValueError("invalid_matched_study_arm")
    if arm["profile"] is not None and arm["profile"] not in {"efficient", "balanced", "frontier"}:
        raise ValueError("invalid_matched_study_arm")
    if arm["verification_status"] not in VERIFICATION_STATUSES:
        raise ValueError("invalid_matched_study_arm")
    if arm["accepted"] is not None and not isinstance(arm["accepted"], bool):
        raise ValueError("invalid_matched_study_arm")
    for field in MATCHED_ARM_FIELDS - {"route", "profile", "terminal_status", "verification_status", "accepted", "failure_codes", "policy_revision"}:
        observed = _nullable_non_negative(arm[field], field)
        if field in MATCHED_COUNT_FIELDS and observed is not None and not isinstance(observed, int):
            raise ValueError(f"invalid_{field}")
    if not isinstance(arm["failure_codes"], list) or any(code not in REASON_CODES for code in arm["failure_codes"]):
        raise ValueError("invalid_matched_failure_codes")
    if arm["policy_revision"] is not None and (
        not isinstance(arm["policy_revision"], str)
        or len(arm["policy_revision"]) != 64
        or any(char not in "0123456789abcdef" for char in arm["policy_revision"])
    ):
        raise ValueError("invalid_policy_revision")
    return arm


def _validate_matched_manifest(manifest: dict[str, Any]) -> None:
    root = _exact(manifest, MATCHED_ROOT_FIELDS, "matched_study_manifest")
    if root["contract_version"] != MATCHED_CAPTURE_VERSION or root["mode"] not in {"dry_run", "live"} or root["evidence_status"] not in {"synthetic", "observed"}:
        raise ValueError("invalid_matched_study_manifest")
    _opaque_identifier(root["study_id"], "study_id")
    _opaque_identifier(root["sampling_contract_id"], "sampling_contract_id")
    if not isinstance(root["pairs"], list) or not root["pairs"]:
        raise ValueError("invalid_matched_study_manifest")
    seen: set[str] = set()
    for value in root["pairs"]:
        pair = _exact(value, MATCHED_PAIR_FIELDS, "matched_study_pair")
        match_id = _opaque_identifier(pair["match_id"], "match_id")
        if match_id in seen:
            raise ValueError("duplicate_match_id")
        seen.add(match_id)
        _task_class(pair["task_class"])
        if pair["acceptance_source"] not in ACCEPTANCE_SOURCES or pair["arm_order"] not in ARM_ORDERS:
            raise ValueError("invalid_matched_study_pair")
        if not all(_opaque_identifier(pair[field], field) for field in ("environment_revision", "verifier_id", "acceptance_contract_id")):
            raise ValueError("invalid_matched_study_pair")
        if not isinstance(pair["budget"], int) or isinstance(pair["budget"], bool) or pair["budget"] < 0:
            raise ValueError("invalid_matched_study_pair")
        if not isinstance(pair["timeout_ms"], int) or isinstance(pair["timeout_ms"], bool) or pair["timeout_ms"] < 1:
            raise ValueError("invalid_matched_study_pair")
        if pair["acceptance_source"] == "gold":
            if not isinstance(pair["gold_accepted"], bool):
                raise ValueError("missing_gold_acceptance")
        elif pair["gold_accepted"] is not None:
            raise ValueError("unexpected_gold_acceptance")
        control, candidate = _validate_matched_arm(pair["control"]), _validate_matched_arm(pair["candidate"])
        if pair["acceptance_source"] == "none" and (control["accepted"] is not None or candidate["accepted"] is not None):
            raise ValueError("unexpected_acceptance")
        if pair["acceptance_source"] in {"gold", "verifier"} and (control["accepted"] is None or candidate["accepted"] is None):
            raise ValueError("missing_acceptance")


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Validate exact allowlists so task text, paths, prompts, and outputs fail closed."""
    if isinstance(manifest, dict) and manifest.get("contract_version") == MATCHED_CAPTURE_VERSION:
        _validate_matched_manifest(manifest)
        return
    root = _exact(manifest, ROOT_FIELDS, "offload_study_manifest")
    if root["contract_version"] != CONTRACT_VERSION or root["mode"] not in {"dry_run", "live"} or root["evidence_status"] not in {"synthetic", "observed"}:
        raise ValueError("invalid_offload_study_manifest")
    _opaque_identifier(root["study_id"], "study_id")
    if not isinstance(root["pairs"], list) or not root["pairs"]:
        raise ValueError("invalid_offload_study_manifest")
    seen: set[str] = set()
    for value in root["pairs"]:
        pair = _exact(value, PAIR_FIELDS, "offload_study_pair")
        match_id = _opaque_identifier(pair["match_id"], "match_id")
        if match_id in seen:
            raise ValueError("duplicate_match_id")
        seen.add(match_id)
        _task_class(pair["task_class"])
        if pair["acceptance_source"] not in ACCEPTANCE_SOURCES:
            raise ValueError("invalid_acceptance_source")
        if pair["acceptance_source"] == "gold":
            if not isinstance(pair["gold_accepted"], bool):
                raise ValueError("missing_gold_acceptance")
        elif pair["gold_accepted"] is not None:
            raise ValueError("unexpected_gold_acceptance")
        control, candidate = _validate_arm(pair["control"]), _validate_arm(pair["candidate"])
        if pair["acceptance_source"] == "none" and (control["accepted"] is not None or candidate["accepted"] is not None):
            raise ValueError("unexpected_acceptance")
        if pair["acceptance_source"] in {"gold", "verifier"} and (control["accepted"] is None or candidate["accepted"] is None):
            raise ValueError("missing_acceptance")


def _percent_delta(candidate: int | None, control: int | None) -> float | None:
    if candidate is None or control is None or control == 0:
        return None
    return round((candidate - control) * 100 / control, 4)


def _provider_total(arm: dict[str, Any]) -> int | None:
    inputs, outputs = arm["provider_input_tokens"], arm["provider_output_tokens"]
    return None if inputs is None or outputs is None else inputs + outputs


def _matched_metric(arm: dict[str, Any], name: str) -> int | float | None:
    if name == "provider_total_tokens":
        return _provider_total(arm)
    if name == "total_tool_calls":
        agent, ldw = arm["agent_tool_calls"], arm["ldw_tool_calls"]
        return None if agent is None or ldw is None else agent + ldw
    return arm[name]


def _metric(values: list[float | None]) -> dict[str, Any]:
    observed = [value for value in values if value is not None]
    return {"observed_pair_count": len(observed), "median_delta_percent": round(statistics.median(observed), 4) if observed else None}


def _false_outcomes(pair: dict[str, Any], arm_name: str) -> tuple[int, int]:
    if pair["acceptance_source"] != "gold":
        return 0, 0
    accepted = pair[arm_name]["accepted"]
    gold = pair["gold_accepted"]
    return int(accepted is True and gold is False), int(accepted is False and gold is True)


def analyze_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return exportable evidence and an AI-OS-only review verdict."""
    if isinstance(manifest, dict) and manifest.get("contract_version") == MATCHED_CAPTURE_VERSION:
        return _analyze_matched_manifest(manifest)
    validate_manifest(manifest)
    metric_values = {name: [] for name in ("latency_ms", "provider_total_tokens", "context_bytes", "local_compute_ms")}
    candidate_local_compute: list[int | None] = []
    false_accept = Counter()
    false_reject = Counter()
    failures: Counter[str] = Counter()
    complete_pairs = 0
    for pair in manifest["pairs"]:
        control, candidate = pair["control"], pair["candidate"]
        accepted_pair = pair["acceptance_source"] == "none" or (control["accepted"] is True and candidate["accepted"] is True)
        verified = control["verification_status"] in {"passed", "observed_success"} and candidate["verification_status"] in {"passed", "observed_success", "schema_valid"}
        if accepted_pair and verified:
            complete_pairs += 1
        metric_values["latency_ms"].append(_percent_delta(candidate["latency_ms"], control["latency_ms"]))
        metric_values["provider_total_tokens"].append(_percent_delta(_provider_total(candidate), _provider_total(control)))
        metric_values["context_bytes"].append(_percent_delta(candidate["context_bytes"], control["context_bytes"]))
        metric_values["local_compute_ms"].append(_percent_delta(candidate["local_compute_ms"], control["local_compute_ms"]))
        candidate_local_compute.append(candidate["local_compute_ms"])
        for arm_name in ("control", "candidate"):
            fa, fr = _false_outcomes(pair, arm_name)
            false_accept[arm_name] += fa
            false_reject[arm_name] += fr
            failure_code = pair[arm_name]["failure_code"]
            if failure_code is not None:
                failures[f"{arm_name}:{failure_code}"] += 1
    limitations = []
    if manifest["mode"] == "dry_run" or manifest["evidence_status"] != "observed":
        verdict, review_status = "INSUFFICIENT_EVIDENCE", "INFORMATIONAL_ONLY"
        limitations.append("synthetic_or_unobserved_evidence_cannot_support_review")
    elif false_accept["candidate"] or false_reject["candidate"]:
        verdict, review_status = "STOP", "SAFETY_REVIEW_REQUIRED"
        limitations.append("candidate_gold_disagreement_requires_investigation")
    elif complete_pairs < MIN_LIVE_PAIRS:
        verdict, review_status = "INSUFFICIENT_EVIDENCE", "NOT_ENOUGH_MATCHED_PAIRS"
        limitations.append("minimum_three_complete_observed_pairs_not_met")
    else:
        verdict, review_status = "READY_FOR_AI_OS_REVIEW", "EVIDENCE_EXPORT_READY"
        limitations.append("ai_os_remains_the_only_promotion_authority")
    metrics = {name: _metric(values) for name, values in metric_values.items()}
    local_observed = [value for value in candidate_local_compute if value is not None]
    metrics["local_compute_burden_ms"] = {
        "observed_candidate_count": len(local_observed),
        "median_candidate_ms": round(statistics.median(local_observed), 4) if local_observed else None,
    }
    match_ids = [pair["match_id"] for pair in manifest["pairs"]]
    return {
        "contract_version": CONTRACT_VERSION,
        "study_id": manifest["study_id"],
        "mode": manifest["mode"],
        "evidence_status": manifest["evidence_status"],
        "verdict": verdict,
        "review_status": review_status,
        "promotion_authority": "ai_os_only",
        "matched_task_ids": match_ids,
        "pair_count": len(match_ids),
        "complete_pair_count": complete_pairs,
        "paired_metrics": metrics,
        "fallback_and_escalation": {
            "control_fallback_count": sum(pair["control"]["fallback_count"] for pair in manifest["pairs"]),
            "candidate_fallback_count": sum(pair["candidate"]["fallback_count"] for pair in manifest["pairs"]),
            "control_escalation_count": sum(pair["control"]["escalation_count"] for pair in manifest["pairs"]),
            "candidate_escalation_count": sum(pair["candidate"]["escalation_count"] for pair in manifest["pairs"]),
        },
        "safety": {
            "false_accept_count": dict(false_accept),
            "false_reject_count": dict(false_reject),
            "failure_counts": dict(sorted(failures.items())),
            "limitations": limitations,
        },
        "evidence_export": {
            "format": "offload_effect_study_v1",
            "manifest_sha256": stable_hash(manifest),
            "study_id": manifest["study_id"],
            "matched_task_ids": match_ids,
            "promotion_authority": "ai_os_only",
        },
        "privacy": {
            "raw_task_ids_persisted": False,
            "raw_tasks_or_paths_persisted": False,
            "prompts_or_model_responses_persisted": False,
            "model_or_provider_invoked": False,
        },
    }


def _analyze_matched_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Analyze a complete, opaque task journey without deriving missing measurements."""
    validate_manifest(manifest)
    values = {name: [] for name in MATCHED_METRICS}
    failures: Counter[str] = Counter()
    outliers = []
    complete_pairs = 0
    measurement_incomplete = []
    task_success_regression = False
    gold_acceptance_disagreement_count = 0
    for pair in manifest["pairs"]:
        control, candidate = pair["control"], pair["candidate"]
        accepted_pair = pair["acceptance_source"] == "none" or (control["accepted"] is True and candidate["accepted"] is True)
        verified = control["verification_status"] in {"passed", "observed_success"} and candidate["verification_status"] in {"passed", "observed_success"}
        if accepted_pair and verified:
            complete_pairs += 1
        if control["accepted"] is True and candidate["accepted"] is False:
            task_success_regression = True
        if pair["acceptance_source"] == "gold":
            gold_acceptance_disagreement_count += sum(
                arm["accepted"] is not pair["gold_accepted"]
                for arm in (control, candidate)
            )
        missing = sorted(
            field for field in REQUIRED_END_TO_END_FIELDS
            if control[field] is None or candidate[field] is None
        )
        if missing:
            measurement_incomplete.append({"match_id": pair["match_id"], "fields": missing})
        for name in MATCHED_METRICS:
            values[name].append(_percent_delta(_matched_metric(candidate, name), _matched_metric(control, name)))
        for arm_name, arm in (("control", control), ("candidate", candidate)):
            for code in arm["failure_codes"]:
                failures[f"{arm_name}:{code}"] += 1
        outliers.append({
            "match_id": pair["match_id"], "task_class": pair["task_class"],
            "accepted": {"control": control["accepted"], "candidate": candidate["accepted"]},
            "verification": {"control": control["verification_status"], "candidate": candidate["verification_status"]},
            "routes": {"control": control["route"], "candidate": candidate["route"]},
            "failure_codes": {"control": control["failure_codes"], "candidate": candidate["failure_codes"]},
            "measurement_complete": not missing,
        })
    if manifest["mode"] == "dry_run" or manifest["evidence_status"] != "observed":
        verdict, review_status = "INSUFFICIENT_EVIDENCE", "INFORMATIONAL_ONLY"
    elif task_success_regression:
        verdict, review_status = "STOP", "TASK_SUCCESS_REGRESSION"
    elif gold_acceptance_disagreement_count:
        verdict, review_status = "STOP", "GOLD_ACCEPTANCE_DISAGREEMENT"
    elif complete_pairs < MIN_LIVE_PAIRS:
        verdict, review_status = "INSUFFICIENT_EVIDENCE", "NOT_ENOUGH_MATCHED_PAIRS"
    elif measurement_incomplete:
        verdict, review_status = "INSUFFICIENT_EVIDENCE", "MEASUREMENT_INCOMPLETE"
    else:
        verdict, review_status = "READY_FOR_AI_OS_REVIEW", "EVIDENCE_EXPORT_READY"
    return {
        "contract_version": MATCHED_CAPTURE_VERSION,
        "study_id": manifest["study_id"], "sampling_contract_id": manifest["sampling_contract_id"],
        "mode": manifest["mode"], "evidence_status": manifest["evidence_status"],
        "verdict": verdict, "review_status": review_status, "promotion_authority": "ai_os_only",
        "matched_task_ids": [pair["match_id"] for pair in manifest["pairs"]],
        "pair_count": len(manifest["pairs"]), "complete_pair_count": complete_pairs,
        "task_success_regression": task_success_regression,
        "gold_acceptance_disagreement_count": gold_acceptance_disagreement_count,
        "paired_metrics": {name: _metric(series) for name, series in values.items()},
        "measurement_incomplete": measurement_incomplete,
        "failure_reason_counts": dict(sorted(failures.items())),
        "pair_outcomes": outliers,
        "evidence_export": {
            "format": "offload_effect_study_v1_1", "manifest_sha256": stable_hash(manifest),
            "study_id": manifest["study_id"], "sampling_contract_id": manifest["sampling_contract_id"],
            "matched_task_ids": [pair["match_id"] for pair in manifest["pairs"]],
            "promotion_authority": "ai_os_only",
        },
        "privacy": {
            "raw_task_ids_persisted": False, "raw_tasks_or_paths_persisted": False,
            "prompts_or_model_responses_persisted": False, "model_or_provider_invoked": False,
        },
    }


def offload_evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    """CLI adapter; invalid evidence stays visible as invalid input."""
    raw = canonical_json(payload)
    try:
        data = analyze_manifest(payload)
    except ValueError as exc:
        return result("offload_effect_study", "stdin", raw, {}, status="invalid_input", errors=[{"code": str(exc)}])
    status = "success" if data["review_status"] == "EVIDENCE_EXPORT_READY" else "partial"
    return result("offload_effect_study", "stdin", raw, data, status=status)
