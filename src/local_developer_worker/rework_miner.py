"""Deterministically summarize caller-supplied, privacy-safe rework evidence."""
from __future__ import annotations

from collections import Counter
from typing import Any

from .contracts import canonical_json, result, stable_hash

ROOT = {"contract_version", "cohort_id", "observations"}
OBSERVATION = {"observation_id", "session_id", "root_class", "signal", "occurrence_count", "evidence_refs"}
ROOT_CLASSES = {"scope", "evidence", "acceptance", "role_routing", "execution", "observability", "workspace_hygiene"}
SIGNALS = {"turn_aborted", "thread_rolled_back", "context_compacted", "repeated_user_message", "repeated_tool_call", "other_observed"}


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 64 or not all(c.isascii() and (c.isupper() or c.isdigit() or c in "_-") for c in value):
        raise ValueError(f"invalid_{label}")
    return value


def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != ROOT or payload.get("contract_version") != "1.0.0":
        raise ValueError("invalid_rework_study")
    _id(payload["cohort_id"], "cohort_id")
    observations = payload["observations"]
    if not isinstance(observations, list) or not observations:
        raise ValueError("invalid_rework_study")
    seen, grouped = set(), Counter()
    refs: dict[tuple[str, str], list[str]] = {}
    for item in observations:
        if not isinstance(item, dict) or set(item) != OBSERVATION:
            raise ValueError("invalid_rework_observation")
        _id(item["session_id"], "session_id")
        observation_id = _id(item["observation_id"], "observation_id")
        if observation_id in seen: raise ValueError("duplicate_observation_id")
        seen.add(observation_id)
        if item["root_class"] not in ROOT_CLASSES or item["signal"] not in SIGNALS:
            raise ValueError("invalid_rework_observation")
        if not isinstance(item["occurrence_count"], int) or isinstance(item["occurrence_count"], bool) or item["occurrence_count"] < 1:
            raise ValueError("invalid_occurrence_count")
        if not isinstance(item["evidence_refs"], list) or not item["evidence_refs"] or any(not isinstance(v, str) or len(v) > 64 for v in item["evidence_refs"]):
            raise ValueError("invalid_evidence_refs")
        key = (item["root_class"], item["signal"])
        grouped[key] += item["occurrence_count"]
        refs.setdefault(key, []).extend(item["evidence_refs"])
    candidates = [{"candidate_id": f"CANDIDATE_{n:03d}", "root_class": root, "signal": signal,
                   "occurrence_count": count, "evidence_refs": sorted(set(refs[(root, signal)])),
                   "promotion_status": "candidate_only"}
                  for n, ((root, signal), count) in enumerate(sorted(grouped.items(), key=lambda x: (-x[1], x[0])), 1)]
    by_root_class = {root: sum(value for (observed_root, _), value in grouped.items() if observed_root == root)
                     for root in sorted(ROOT_CLASSES) if any(observed_root == root for observed_root, _ in grouped)}
    return {"contract_version": "1.0.0", "cohort_id": payload["cohort_id"], "candidate_count": len(candidates),
            "candidates": candidates, "summary": {"observations": len(observations), "total_occurrences": sum(grouped.values()), "by_root_class": by_root_class},
            "promotion_authority": "human_or_ai_os_only", "privacy": {"raw_session_content_persisted": False, "model_invoked": False},
            "evidence_export": {"format": "rework_miner_v1", "input_sha256": stable_hash(payload)}}


def learn_analyze(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    try: data = analyze(payload)
    except ValueError as exc: return result("rework_miner", "stdin", raw, {}, status="invalid_input", errors=[{"code": str(exc)}])
    return result("rework_miner", "stdin", raw, data)
