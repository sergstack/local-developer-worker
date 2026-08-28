"""Analyze supplied paired replay facts; never launch an agent or provider."""
from __future__ import annotations

import json
import statistics
from typing import Any

METRICS = ("context_bytes", "tool_calls", "latency_ms")
RUN = {"context_bytes", "tool_calls", "latency_ms", "task_accepted"}
PAIR_V1 = {"pair_id", "environment_revision", "budget", "timeout_ms", "verifier_id", "baseline", "candidate"}
PAIR_V11 = PAIR_V1 | {"baseline_evidence_id", "candidate_evidence_id"}
ROOT_V1 = {"contract_version", "mode", "baseline_revision", "candidate_revision", "pairs"}
ROOT_V11 = ROOT_V1 | {"evidence_status", "owner_approval_id", "materiality_threshold_percent"}
CAPTURE = {
    "pair_id", "arm", "evidence_id", "task_id", "environment_revision", "budget", "timeout_ms", "verifier_id",
    "context_bytes", "estimated_input_tokens", "observed_input_tokens", "files_selected", "context_expansions",
    "tool_calls", "latency_ms", "task_accepted", "provider_cost_usd",
}
CAPTURE_STUDY = ROOT_V11 - {"pairs"} | {"captures"}
OBSERVED_TOOL_ITEM_TYPES = frozenset({"command_execution", "custom_tool_call", "function_call", "mcp_tool_call", "web_search"})


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


def _valid_capture(capture: Any) -> bool:
    if not isinstance(capture, dict) or set(capture) != CAPTURE:
        return False
    if capture["arm"] not in {"baseline", "candidate"}:
        return False
    if not all(_is_nonempty_string(capture[field]) for field in ("pair_id", "evidence_id", "task_id", "environment_revision", "verifier_id")):
        return False
    if not isinstance(capture["budget"], (int, float)) or isinstance(capture["budget"], bool) or capture["budget"] < 0:
        return False
    if not isinstance(capture["timeout_ms"], int) or isinstance(capture["timeout_ms"], bool) or capture["timeout_ms"] < 1:
        return False
    integer_fields = ("context_bytes", "estimated_input_tokens", "files_selected", "context_expansions", "tool_calls", "latency_ms")
    if any(not isinstance(capture[field], int) or isinstance(capture[field], bool) or capture[field] < 0 for field in integer_fields):
        return False
    if capture["observed_input_tokens"] is not None and (not isinstance(capture["observed_input_tokens"], int) or isinstance(capture["observed_input_tokens"], bool) or capture["observed_input_tokens"] < 0):
        return False
    if capture["provider_cost_usd"] is not None and (not isinstance(capture["provider_cost_usd"], (int, float)) or isinstance(capture["provider_cost_usd"], bool) or capture["provider_cost_usd"] < 0):
        return False
    return isinstance(capture["task_accepted"], bool)


def observe_agent_jsonl(text: str) -> dict[str, int | bool | None]:
    """Reduce transient Codex JSONL to allowed aggregate replay evidence.

    The caller owns the stream lifetime. This function retains no event, thread
    ID, command, prompt, tool argument, or provider text.
    """
    completed = False
    tool_calls = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "turn.completed":
            completed = True
            usage = event.get("usage")
            if isinstance(usage, dict):
                for field in ("input_tokens", "output_tokens"):
                    value = usage.get(field)
                    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                        if field == "input_tokens":
                            input_tokens = value
                        else:
                            output_tokens = value
        elif event.get("type") == "item.started":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") in OBSERVED_TOOL_ITEM_TYPES:
                tool_calls += 1
    return {
        "completed": completed,
        "tool_calls": tool_calls,
        "observed_input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def build_replay_manifest(study: dict[str, Any]) -> dict[str, Any]:
    """Convert supplied aggregate arm captures into the v1.1 replay manifest.

    This is deliberately a pure boundary: callers retain the supplied evidence
    records, while the analyzer receives only the three promotion metrics and
    opaque evidence IDs.  It never reads a transcript, calls a provider, starts
    an agent, or persists data.
    """
    if not isinstance(study, dict) or set(study) != CAPTURE_STUDY:
        raise ValueError("invalid_capture_study")
    if study["contract_version"] != "1.1.0" or study["mode"] != "live" or study["evidence_status"] != "observed":
        raise ValueError("invalid_capture_study")
    if not all(_is_nonempty_string(study[field]) for field in ("baseline_revision", "candidate_revision", "owner_approval_id")) or study["baseline_revision"] == study["candidate_revision"] or not _valid_thresholds(study["materiality_threshold_percent"]):
        raise ValueError("invalid_capture_study")
    captures = study["captures"]
    if not isinstance(captures, list) or not captures or not all(_valid_capture(capture) for capture in captures):
        raise ValueError("invalid_capture_study")
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for capture in captures:
        arms = grouped.setdefault(capture["pair_id"], {})
        if capture["arm"] in arms:
            raise ValueError("invalid_capture_study")
        arms[capture["arm"]] = capture
    pairs = []
    shared_fields = ("environment_revision", "budget", "timeout_ms", "verifier_id")
    for pair_id in sorted(grouped):
        arms = grouped[pair_id]
        if set(arms) != {"baseline", "candidate"}:
            raise ValueError("invalid_capture_study")
        baseline, candidate = arms["baseline"], arms["candidate"]
        if baseline["evidence_id"] == candidate["evidence_id"] or baseline["task_id"] != candidate["task_id"] or any(baseline[field] != candidate[field] for field in shared_fields):
            raise ValueError("invalid_capture_study")
        pairs.append({
            "pair_id": pair_id,
            "environment_revision": baseline["environment_revision"],
            "budget": baseline["budget"],
            "timeout_ms": baseline["timeout_ms"],
            "verifier_id": baseline["verifier_id"],
            "baseline_evidence_id": baseline["evidence_id"],
            "candidate_evidence_id": candidate["evidence_id"],
            "baseline": {field: baseline[field] for field in RUN},
            "candidate": {field: candidate[field] for field in RUN},
        })
    return {
        "contract_version": "1.1.0",
        "mode": "live",
        "baseline_revision": study["baseline_revision"],
        "candidate_revision": study["candidate_revision"],
        "evidence_status": "observed",
        "owner_approval_id": study["owner_approval_id"],
        "materiality_threshold_percent": study["materiality_threshold_percent"],
        "pairs": pairs,
    }


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
