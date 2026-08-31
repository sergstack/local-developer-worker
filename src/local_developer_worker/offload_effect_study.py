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


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Validate exact allowlists so task text, paths, prompts, and outputs fail closed."""
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


def offload_evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    """CLI adapter; invalid evidence stays visible as invalid input."""
    raw = canonical_json(payload)
    try:
        data = analyze_manifest(payload)
    except ValueError as exc:
        return result("offload_effect_study", "stdin", raw, {}, status="invalid_input", errors=[{"code": str(exc)}])
    status = "success" if data["review_status"] == "EVIDENCE_EXPORT_READY" else "partial"
    return result("offload_effect_study", "stdin", raw, data, status=status)
