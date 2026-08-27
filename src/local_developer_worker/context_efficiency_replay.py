"""Analyze supplied paired replay facts; never launch an agent or provider."""
from __future__ import annotations

import statistics
from typing import Any

RUN = {"context_bytes", "tool_calls", "latency_ms", "task_accepted"}
PAIR = {"pair_id", "environment_revision", "budget", "timeout_ms", "verifier_id", "baseline", "candidate"}


def analyze_replay(manifest: dict[str, Any]) -> dict[str, Any]:
    if set(manifest) != {"contract_version", "mode", "pairs"} or manifest["contract_version"] != "1.0.0" or manifest["mode"] not in {"dry_run", "live"} or not isinstance(manifest["pairs"], list) or not manifest["pairs"]:
        raise ValueError("invalid_replay_manifest")
    deltas, accepted = [], []
    for pair in manifest["pairs"]:
        if set(pair) != PAIR or not all(isinstance(pair[field], str) and pair[field] for field in ("pair_id", "environment_revision", "verifier_id")) or not isinstance(pair["budget"], (int, float)) or isinstance(pair["budget"], bool) or pair["budget"] < 0 or not isinstance(pair["timeout_ms"], int) or isinstance(pair["timeout_ms"], bool) or pair["timeout_ms"] < 1:
            raise ValueError("invalid_replay_pair")
        for arm in ("baseline", "candidate"):
            run = pair[arm]
            if not isinstance(run, dict) or set(run) != RUN or not isinstance(run["task_accepted"], bool) or any(not isinstance(run[field], int) or isinstance(run[field], bool) or run[field] < 0 for field in RUN - {"task_accepted"}):
                raise ValueError("invalid_replay_run")
        base, candidate = pair["baseline"], pair["candidate"]
        deltas.append({field: round((candidate[field] - base[field]) * 100 / base[field], 4) if base[field] else None for field in ("context_bytes", "tool_calls", "latency_ms")})
        accepted.append((base["task_accepted"], candidate["task_accepted"]))
    success_regression = any(base and not candidate for base, candidate in accepted)
    medians = {field: statistics.median([item[field] for item in deltas if item[field] is not None]) if any(item[field] is not None for item in deltas) else None for field in ("context_bytes", "tool_calls", "latency_ms")}
    verdict = "REVISE" if manifest["mode"] == "dry_run" else "STOP" if success_regression else "PASS" if any(value is not None and value < 0 for value in medians.values()) else "REVISE"
    return {"contract_version": "1.0.0", "mode": manifest["mode"], "verdict": verdict, "pair_count": len(manifest["pairs"]), "task_success_regression": success_regression, "median_delta_percent": medians, "provider_calls": False}
