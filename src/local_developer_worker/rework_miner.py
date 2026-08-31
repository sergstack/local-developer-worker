"""Deterministically summarize caller-supplied, privacy-safe rework evidence."""
from __future__ import annotations

from collections import Counter
from typing import Any

from .contracts import canonical_json, result, stable_hash

ROOT = {"contract_version", "cohort_id", "observations"}
OBSERVATION = {"observation_id", "session_id", "root_class", "signal", "occurrence_count", "evidence_refs"}
ROOT_CLASSES = {"scope", "evidence", "acceptance", "role_routing", "execution", "observability", "workspace_hygiene"}
SIGNALS = {"turn_aborted", "thread_rolled_back", "context_compacted", "repeated_user_message", "repeated_tool_call", "other_observed"}
CANDIDATE_LESSON_ROOT = {"contract_version", "candidate", "allowed_evidence_refs"}
CANDIDATE_LESSON = {
    "candidate_id", "trigger", "observed_problem", "human_correction", "rework_class",
    "generalizable_rule", "scope", "counterexamples", "evidence_refs", "occurrence_count",
    "candidate_destination", "confidence",
}
CANDIDATE_DESTINATIONS = {"regression", "skill", "ai_os_rule", "execution_handling", "reject"}
CONFIDENCE = {"low", "medium", "high"}


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 64 or not all(c.isascii() and (c.isupper() or c.isdigit() or c in "_-") for c in value):
        raise ValueError(f"invalid_{label}")
    return value


def _sanitized_text(value: Any, label: str, limit: int = 1000) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(char) < 32 for char in value):
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


def prepare_sanitized_excerpts(payload: dict[str, Any]) -> dict[str, Any]:
    """Build model-safe structural excerpts from P0 observations.

    The input contract is intentionally identical to P0.  Session IDs are used
    only while validating the caller-supplied input and are not returned.  The
    result is useful for candidate review, but cannot establish the meaning of
    a human correction that was never supplied as sanitized evidence.
    """
    summary = analyze(payload)
    excerpts = []
    for number, candidate in enumerate(summary["candidates"], 1):
        excerpts.append({
            "excerpt_id": f"EXCERPT_{number:03d}",
            "root_class": candidate["root_class"],
            "signal": candidate["signal"],
            "occurrence_count": candidate["occurrence_count"],
            "evidence_refs": candidate["evidence_refs"],
            "sanitized_excerpt": (
                f"Observed structural signal '{candidate['signal']}' in rework class "
                f"'{candidate['root_class']}' with {candidate['occurrence_count']} occurrences."
            ),
            "human_correction_status": "not_observed",
        })
    return {
        "contract_version": "1.0.0",
        "cohort_id": summary["cohort_id"],
        "excerpt_count": len(excerpts),
        "excerpts": excerpts,
        "privacy": {
            "raw_session_content_read": False,
            "raw_session_content_persisted": False,
            "session_ids_exported": False,
            "model_invoked": False,
        },
        "limitations": ["human_correction_not_observed_in_structural_input"],
        "evidence_export": {"format": "rework_structural_excerpt_v1", "input_sha256": stable_hash(payload)},
    }


def learn_prepare_excerpts(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    try:
        data = prepare_sanitized_excerpts(payload)
    except ValueError as exc:
        return result("rework_excerpt_preparer", "stdin", raw, {}, status="invalid_input", errors=[{"code": str(exc)}])
    return result("rework_excerpt_preparer", "stdin", raw, data)


def validate_candidate_lesson(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a caller-supplied, already-sanitized candidate lesson.

    This boundary deliberately does not read sessions or invoke a model.  It
    proves only shape and opaque-evidence lineage; a Judge and owner remain
    required before a candidate can be reused or promoted.
    """
    if not isinstance(payload, dict) or set(payload) != CANDIDATE_LESSON_ROOT or payload.get("contract_version") != "1.0.0":
        raise ValueError("invalid_candidate_lesson_study")
    allowed_refs = payload["allowed_evidence_refs"]
    if not isinstance(allowed_refs, list) or not allowed_refs:
        raise ValueError("invalid_allowed_evidence_refs")
    allowed = {_id(value, "allowed_evidence_ref") for value in allowed_refs}
    if len(allowed) != len(allowed_refs):
        raise ValueError("duplicate_allowed_evidence_ref")
    candidate = payload["candidate"]
    if not isinstance(candidate, dict) or set(candidate) != CANDIDATE_LESSON:
        raise ValueError("invalid_candidate_lesson")
    _id(candidate["candidate_id"], "candidate_id")
    for field in ("trigger", "observed_problem", "human_correction", "generalizable_rule", "scope"):
        _sanitized_text(candidate[field], field)
    counterexamples = candidate["counterexamples"]
    if not isinstance(counterexamples, list) or any(_sanitized_text(item, "counterexample", 500) != item for item in counterexamples):
        raise ValueError("invalid_counterexamples")
    if candidate["rework_class"] not in ROOT_CLASSES:
        raise ValueError("invalid_rework_class")
    if candidate["candidate_destination"] not in CANDIDATE_DESTINATIONS or candidate["confidence"] not in CONFIDENCE:
        raise ValueError("invalid_candidate_disposition")
    if not isinstance(candidate["occurrence_count"], int) or isinstance(candidate["occurrence_count"], bool) or candidate["occurrence_count"] < 1:
        raise ValueError("invalid_occurrence_count")
    refs = candidate["evidence_refs"]
    if not isinstance(refs, list) or not refs:
        raise ValueError("invalid_evidence_refs")
    checked_refs = [_id(value, "evidence_ref") for value in refs]
    if len(set(checked_refs)) != len(checked_refs):
        raise ValueError("duplicate_evidence_ref")
    if not set(checked_refs).issubset(allowed):
        raise ValueError("unknown_evidence_ref")
    return {
        "contract_version": "1.0.0",
        "candidate": candidate,
        "validation": {"schema": "passed", "evidence_references": "passed", "promotion_status": "candidate_only", "reuse_status": "judge_required"},
        "privacy": {"raw_session_content_read": False, "raw_session_content_persisted": False, "model_invoked": False},
        "evidence_export": {"format": "candidate_lesson_v1", "input_sha256": stable_hash(payload)},
    }


def learn_validate_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    try:
        data = validate_candidate_lesson(payload)
    except ValueError as exc:
        return result("candidate_lesson_validator", "stdin", raw, {}, status="invalid_input", errors=[{"code": str(exc)}])
    return result("candidate_lesson_validator", "stdin", raw, data)
