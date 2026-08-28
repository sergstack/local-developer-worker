"""Analyze supplied paired replay facts; never launch an agent or provider."""
from __future__ import annotations

import statistics
from typing import Any

METRICS = ("context_bytes", "tool_calls", "latency_ms")
RUN = {"context_bytes", "tool_calls", "latency_ms", "task_accepted"}
PAIR_V1 = {"pair_id", "environment_revision", "budget", "timeout_ms", "verifier_id", "baseline", "candidate"}
PAIR_V11 = PAIR_V1 | {"baseline_evidence_id", "candidate_evidence_id"}
ROOT_V1 = {"contract_version", "mode", "baseline_revision", "candidate_revision", "pairs"}
ROOT_V11 = ROOT_V1 | {"evidence_status", "owner_approval_id", "materiality_threshold_percent"}


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _valid_thresholds(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == set(METRICS)
        and all(
            isinstance(value[metric], (int, float))
            and not isinstance(value[metric], bool)
            and value[metric] > 0
            for metric in METRICS
        )
    )


def _materiality(medians: dict[str, float | None], manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest["contract_version"] != "1.1.0":
        return {"approval_id": None, "evidence_status": None, "threshold_percent": None, "all_required_metrics_met": False}
    thresholds = manifest["materiality_threshold_percent"]
    return {
        "approval_id": manifest["owner_approval_id"],
        "evidence_status": manifest["evidence_status"],
        "threshold_percent": thresholds,
        "all_required_metrics_met": all(medians[metric] is not None and medians[metric] <= -thresholds[metric] for metric in METRICS),
    }


def analyze_replay(manifest: dict[str, Any]) -> dict[str, Any]:
    version = manifest.get("contract_version") if isinstance(manifest, dict) else None
    root = ROOT_V1 if version == "1.0.0" else ROOT_V11 if version == "1.1.0" else set()
    if not isinstance(manifest, dict) or set(manifest) != root or manifest["mode"] not in {"dry_run", "live"} or not all(_is_nonempty_string(manifest[field]) for field in ("baseline_revision", "candidate_revision")) or not isinstance(manifest["pairs"], list) or not manifest["pairs"]:
        raise ValueError("invalid_replay_manifest")
    if version == "1.1.0" and (manifest["evidence_status"] not in {"observed", "synthetic"} or not _is_nonempty_string(manifest["owner_approval_id"]) or not _valid_thresholds(manifest["materiality_threshold_percent"])):
        raise ValueError("invalid_replay_manifest")
    deltas, accepted, pair_outcomes = [], [], []
    required_pair = PAIR_V1 if version == "1.0.0" else PAIR_V11
    for pair in manifest["pairs"]:
        if not isinstance(pair, dict) or set(pair) != required_pair or not all(_is_nonempty_string(pair[field]) for field in ("pair_id", "environment_revision", "verifier_id")) or (version == "1.1.0" and not all(_is_nonempty_string(pair[field]) for field in ("baseline_evidence_id", "candidate_evidence_id"))) or not isinstance(pair["budget"], (int, float)) or isinstance(pair["budget"], bool) or pair["budget"] < 0 or not isinstance(pair["timeout_ms"], int) or isinstance(pair["timeout_ms"], bool) or pair["timeout_ms"] < 1:
            raise ValueError("invalid_replay_pair")
        for arm in ("baseline", "candidate"):
            run = pair[arm]
            if not isinstance(run, dict) or set(run) != RUN or not isinstance(run["task_accepted"], bool) or any(not isinstance(run[field], int) or isinstance(run[field], bool) or run[field] < 0 for field in RUN - {"task_accepted"}):
                raise ValueError("invalid_replay_run")
        base, candidate = pair["baseline"], pair["candidate"]
        delta = {field: round((candidate[field] - base[field]) * 100 / base[field], 4) if base[field] else None for field in METRICS}
        deltas.append(delta)
        accepted.append((base["task_accepted"], candidate["task_accepted"]))
        pair_outcomes.append({"pair_id": pair["pair_id"], "baseline_task_accepted": base["task_accepted"], "candidate_task_accepted": candidate["task_accepted"], "delta_percent": delta})
    success_regression = any(base and not candidate for base, candidate in accepted)
    medians = {field: statistics.median([item[field] for item in deltas if item[field] is not None]) if any(item[field] is not None for item in deltas) else None for field in METRICS}
    materiality = _materiality(medians, manifest)
    eligible_for_pass = manifest["mode"] == "live" and version == "1.1.0" and materiality["evidence_status"] == "observed" and materiality["all_required_metrics_met"]
    verdict = "REVISE" if manifest["mode"] == "dry_run" else "STOP" if success_regression else "PASS" if eligible_for_pass else "REVISE"
    result = {"contract_version": version, "mode": manifest["mode"], "baseline_revision": manifest["baseline_revision"], "candidate_revision": manifest["candidate_revision"], "verdict": verdict, "pair_count": len(manifest["pairs"]), "task_success_regression": success_regression, "median_delta_percent": medians, "pair_outcomes": pair_outcomes, "provider_calls": False}
    if version == "1.1.0":
        result["materiality"] = materiality
    return result
