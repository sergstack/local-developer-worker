"""Analyze privacy-safe matched evidence for local Ollama advisory suitability.

This module never invokes Codex or Ollama.  It consumes only aggregate arm
measurements supplied by an owner-controlled live-study capture.
"""

from __future__ import annotations

import statistics
from typing import Any


CONTRACT_VERSION = "1.0.0"
MIN_LIVE_PAIRS_PER_CLASS = 5
METRICS = ("development_latency_ms", "codex_provider_tokens", "codex_context_bytes")
ROOT_FIELDS = {"contract_version", "mode", "evidence_status", "study_id", "threshold_percent", "pairs"}
PAIR_FIELDS = {"pair_id", "task_class", "task_kind", "control", "candidate"}
ARM_FIELDS = {
    "accepted", "development_latency_ms", "codex_input_tokens", "codex_output_tokens",
    "codex_context_bytes", "ollama_input_tokens", "ollama_output_tokens", "ollama_latency_ms",
}
TASK_KINDS = {"terminal_deterministic", "codex_review_required"}


def _require_exact(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"invalid_{label}")
    return value


def _non_negative_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"invalid_{label}")
    return value


def _non_negative_int_or_none(value: Any, label: str) -> int | None:
    if value is None:
        return None
    return _non_negative_int(value, label)


def _validate_arm(value: Any) -> dict[str, Any]:
    arm = _require_exact(value, ARM_FIELDS, "study_arm")
    if not isinstance(arm["accepted"], bool):
        raise ValueError("invalid_study_arm")
    for field in {"development_latency_ms", "codex_input_tokens", "codex_output_tokens", "codex_context_bytes"}:
        _non_negative_int(arm[field], field)
    for field in {"ollama_input_tokens", "ollama_output_tokens", "ollama_latency_ms"}:
        _non_negative_int_or_none(arm[field], field)
    return arm


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Reject raw tasks, prompts, outputs, paths, and unknown fields."""
    root = _require_exact(manifest, ROOT_FIELDS, "advisory_study_manifest")
    if (
        root["contract_version"] != CONTRACT_VERSION
        or root["mode"] not in {"dry_run", "live"}
        or root["evidence_status"] not in {"synthetic", "observed"}
    ):
        raise ValueError("invalid_advisory_study_manifest")
    if not isinstance(root["study_id"], str) or not root["study_id"]:
        raise ValueError("invalid_advisory_study_manifest")
    thresholds = _require_exact(root["threshold_percent"], set(METRICS), "advisory_study_thresholds")
    for metric in METRICS:
        if not isinstance(thresholds[metric], (int, float)) or isinstance(thresholds[metric], bool) or thresholds[metric] <= 0:
            raise ValueError("invalid_advisory_study_thresholds")
    if not isinstance(root["pairs"], list) or not root["pairs"]:
        raise ValueError("invalid_advisory_study_manifest")
    seen: set[str] = set()
    for value in root["pairs"]:
        pair = _require_exact(value, PAIR_FIELDS, "advisory_study_pair")
        if not isinstance(pair["pair_id"], str) or not pair["pair_id"] or pair["pair_id"] in seen:
            raise ValueError("invalid_advisory_study_pair")
        seen.add(pair["pair_id"])
        if not isinstance(pair["task_class"], str) or not pair["task_class"] or pair["task_kind"] not in TASK_KINDS:
            raise ValueError("invalid_advisory_study_pair")
        _validate_arm(pair["control"])
        _validate_arm(pair["candidate"])


def _delta(candidate: int, control: int) -> float | None:
    return None if control == 0 else round((candidate - control) * 100 / control, 4)


def _codex_tokens(arm: dict[str, Any]) -> int:
    return arm["codex_input_tokens"] + arm["codex_output_tokens"]


def _pair_metrics(pair: dict[str, Any]) -> dict[str, float | None]:
    control, candidate = pair["control"], pair["candidate"]
    return {
        "development_latency_ms": _delta(candidate["development_latency_ms"], control["development_latency_ms"]),
        "codex_provider_tokens": _delta(_codex_tokens(candidate), _codex_tokens(control)),
        "codex_context_bytes": _delta(candidate["codex_context_bytes"], control["codex_context_bytes"]),
    }


def analyze_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Classify task classes without treating schema validity as task success."""
    validate_manifest(manifest)
    by_class: dict[str, list[dict[str, Any]]] = {}
    for pair in manifest["pairs"]:
        by_class.setdefault(pair["task_class"], []).append(pair)
    classes = []
    for task_class in sorted(by_class):
        pairs = by_class[task_class]
        task_kinds = {pair["task_kind"] for pair in pairs}
        accepted = all(pair["control"]["accepted"] and pair["candidate"]["accepted"] for pair in pairs)
        metric_values = {metric: [value for value in (_pair_metrics(pair)[metric] for pair in pairs) if value is not None] for metric in METRICS}
        medians = {metric: round(statistics.median(values), 4) if values else None for metric, values in metric_values.items()}
        materially_better = all(medians[metric] is not None and medians[metric] <= -manifest["threshold_percent"][metric] for metric in METRICS)
        if manifest["mode"] == "dry_run" or manifest["evidence_status"] != "observed":
            decision, reason = "INSUFFICIENT_EVIDENCE", "synthetic_measurements_cannot_authorize_use"
        elif task_kinds != {"terminal_deterministic"}:
            decision, reason = "DENY", "codex_review_required_adds_an_unmeasured_or_extra_review_loop"
        elif len(pairs) < MIN_LIVE_PAIRS_PER_CLASS:
            decision, reason = "INSUFFICIENT_EVIDENCE", "minimum_five_matched_live_pairs_per_class_not_met"
        elif not accepted:
            decision, reason = "DENY", "verification_or_task_acceptance_failed"
        elif not materially_better:
            decision, reason = "DENY", "all_speed_token_and_context_gates_not_met"
        else:
            decision, reason = "PERMIT", "all_matched_aggregate_gates_met_without_codex_review"
        classes.append({
            "task_class": task_class,
            "task_kinds": sorted(task_kinds),
            "pair_count": len(pairs),
            "accepted_pairs": sum(pair["control"]["accepted"] and pair["candidate"]["accepted"] for pair in pairs),
            "median_delta_percent": medians,
            "decision": decision,
            "reason": reason,
        })
    return {
        "contract_version": CONTRACT_VERSION,
        "study_id": manifest["study_id"],
        "mode": manifest["mode"],
        "evidence_status": manifest["evidence_status"],
        "threshold_percent": manifest["threshold_percent"],
        "task_classes": classes,
        "privacy": {
            "raw_tasks_or_paths_persisted": False,
            "prompts_or_model_responses_persisted": False,
            "ollama_tokens_not_combined_with_codex_provider_tokens": True,
        },
    }
