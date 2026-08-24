"""Deterministic analysis for a privacy-safe Adaptive Routing effect study.

This module never starts Codex, reads a telemetry journal, or changes a policy.
It analyzes only an explicitly supplied, already-sanitized paired-study manifest.
"""

from __future__ import annotations

import random
import statistics
from typing import Any


CONTRACT_VERSION = "1.0.0"
MIN_LIVE_PAIRS = 30
BOOTSTRAP_SAMPLES = 10_000
ARMS = {"control_fixed_balanced", "adaptive"}
ROOT_FIELDS = {"contract_version", "study_id", "study_mode", "arms", "pairs"}
PAIR_FIELDS = {"pair_id", "snapshot_id", "task_class", "control", "adaptive", "context"}
RUN_FIELDS = {
    "execution_status", "verification_status", "latency_ms", "input_tokens",
    "cached_input_tokens", "output_tokens", "reasoning_tokens", "fallback_count",
    "escalation_count",
}
CONTEXT_FIELDS = {"candidate_bytes", "selected_bytes", "critical_recall", "sensitive_block_count"}


def _require_fields(value: dict[str, Any], allowed: set[str], label: str) -> None:
    extra = set(value) - allowed
    missing = allowed - set(value)
    if extra or missing:
        raise ValueError(f"invalid_{label}_fields")


def _number(value: Any, label: str, *, minimum: float = 0) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"invalid_{label}")
    return float(value)


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Reject unknown fields so prompts, paths, and provider output cannot enter."""
    if not isinstance(manifest, dict):
        raise ValueError("invalid_manifest")
    _require_fields(manifest, ROOT_FIELDS, "manifest")
    if manifest["contract_version"] != CONTRACT_VERSION:
        raise ValueError("unsupported_contract_version")
    if manifest["study_mode"] not in {"dry_run", "live"}:
        raise ValueError("invalid_study_mode")
    if not isinstance(manifest["study_id"], str) or not manifest["study_id"]:
        raise ValueError("invalid_study_id")
    if not isinstance(manifest["arms"], dict) or set(manifest["arms"]) != ARMS:
        raise ValueError("invalid_study_arms")
    if manifest["arms"]["control_fixed_balanced"] != {"adaptive_routing": False, "profile": "balanced"}:
        raise ValueError("invalid_control_arm")
    if manifest["arms"]["adaptive"] != {"adaptive_routing": True, "profile": None}:
        raise ValueError("invalid_adaptive_arm")
    if not isinstance(manifest["pairs"], list) or not manifest["pairs"]:
        raise ValueError("invalid_pairs")
    pair_ids: set[str] = set()
    for pair in manifest["pairs"]:
        if not isinstance(pair, dict):
            raise ValueError("invalid_pair")
        _require_fields(pair, PAIR_FIELDS, "pair")
        if not all(isinstance(pair[key], str) and pair[key] for key in ("pair_id", "snapshot_id", "task_class")):
            raise ValueError("invalid_pair_identity")
        if pair["pair_id"] in pair_ids:
            raise ValueError("duplicate_pair_id")
        pair_ids.add(pair["pair_id"])
        for arm in ("control", "adaptive"):
            run = pair[arm]
            if not isinstance(run, dict):
                raise ValueError("invalid_run")
            _require_fields(run, RUN_FIELDS, "run")
            if run["execution_status"] not in {"completed", "blocked", "failed"}:
                raise ValueError("invalid_execution_status")
            if run["verification_status"] not in {"passed", "failed", "uncertain", "not_run"}:
                raise ValueError("invalid_verification_status")
            for field in RUN_FIELDS - {"execution_status", "verification_status"}:
                _number(run[field], field)
            if run["cached_input_tokens"] > run["input_tokens"]:
                raise ValueError("cached_input_exceeds_input")
        context = pair["context"]
        if not isinstance(context, dict):
            raise ValueError("invalid_context")
        _require_fields(context, CONTEXT_FIELDS, "context")
        for field in ("candidate_bytes", "selected_bytes", "sensitive_block_count"):
            _number(context[field], field)
        if context["selected_bytes"] > context["candidate_bytes"]:
            raise ValueError("selected_context_exceeds_candidate")
        if _number(context["critical_recall"], "critical_recall") > 1:
            raise ValueError("invalid_critical_recall")


def _percent_delta(candidate: float, baseline: float) -> float | None:
    if baseline <= 0:
        return None
    return (candidate - baseline) * 100 / baseline


def _quantile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _paired_metric(values: list[float], *, seed: str) -> dict[str, Any]:
    if not values:
        return {"n": 0, "median_delta_percent": None, "bootstrap_ci_95_percent": None}
    generator = random.Random(seed)
    medians = [statistics.median([values[generator.randrange(len(values))] for _ in values]) for _ in range(BOOTSTRAP_SAMPLES)]
    return {
        "n": len(values),
        "median_delta_percent": round(statistics.median(values), 4),
        "bootstrap_ci_95_percent": [round(_quantile(medians, 0.025), 4), round(_quantile(medians, 0.975), 4)],
    }


def _provider_total(run: dict[str, Any]) -> float:
    # Cached input is a subset of input; reasoning is diagnostic with unknown
    # provider inclusion, so neither can be added to this canonical total.
    return float(run["input_tokens"] + run["output_tokens"])


def analyze_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(manifest)
    latency, tokens, context = [], [], []
    complete_pairs = 0
    for pair in manifest["pairs"]:
        control, adaptive = pair["control"], pair["adaptive"]
        completed = all(run["execution_status"] == "completed" and run["verification_status"] == "passed" for run in (control, adaptive))
        if completed:
            complete_pairs += 1
            latency.append(_percent_delta(adaptive["latency_ms"], control["latency_ms"]))
            tokens.append(_percent_delta(_provider_total(adaptive), _provider_total(control)))
        context.append(_percent_delta(pair["context"]["selected_bytes"], pair["context"]["candidate_bytes"]))
    latency = [item for item in latency if item is not None]
    tokens = [item for item in tokens if item is not None]
    context = [item for item in context if item is not None]
    metrics = {
        "latency": _paired_metric(latency, seed=manifest["study_id"] + ":latency"),
        "provider_total_tokens": _paired_metric(tokens, seed=manifest["study_id"] + ":tokens"),
        "selected_context_bytes": _paired_metric(context, seed=manifest["study_id"] + ":context"),
        "token_semantics": {
            "provider_total_tokens": "input_tokens + output_tokens",
            "cached_input_tokens": "subset_of_input_tokens",
            "reasoning_tokens": "diagnostic_only; inclusion_in_output_unknown",
        },
    }
    safety = {
        "critical_recall_min": min(pair["context"]["critical_recall"] for pair in manifest["pairs"]),
        "sensitive_block_count": sum(pair["context"]["sensitive_block_count"] for pair in manifest["pairs"]),
        "complete_pairs": complete_pairs,
        "total_pairs": len(manifest["pairs"]),
    }
    if manifest["study_mode"] == "dry_run":
        verdict, gate_status, reasons = "INSUFFICIENT_EVIDENCE", "INFORMATIONAL_ONLY", ["synthetic_or_dry_run_data_cannot_promote_routing"]
    elif safety["critical_recall_min"] < 1 or safety["sensitive_block_count"] or complete_pairs != len(manifest["pairs"]):
        verdict, gate_status, reasons = "STOP", "BLOCKED", ["safety_or_completion_gate_failed"]
    elif len(manifest["pairs"]) < MIN_LIVE_PAIRS:
        verdict, gate_status, reasons = "INSUFFICIENT_EVIDENCE", "NOT_ENOUGH_LIVE_PAIRS", ["minimum_live_pairs_not_met"]
    else:
        benefits = []
        for name, threshold in (("latency", -15), ("provider_total_tokens", -15), ("selected_context_bytes", -30)):
            metric = metrics[name]
            if metric["median_delta_percent"] <= threshold and metric["bootstrap_ci_95_percent"][1] < 0:
                benefits.append(name)
        verdict, gate_status = ("PASS", "PROMOTION_CANDIDATE") if benefits else ("REVISE", "NO_MATERIAL_BENEFIT")
        reasons = benefits or ["no_metric_met_a_preregistered_benefit_gate"]
    return {
        "contract_version": CONTRACT_VERSION,
        "study_id": manifest["study_id"],
        "study_mode": manifest["study_mode"],
        "gate_status": gate_status,
        "verdict": verdict,
        "reasons": reasons,
        "safety": safety,
        "paired_metrics": metrics,
        "privacy": {"raw_tasks_or_paths_persisted": False, "provider_responses_persisted": False},
    }
