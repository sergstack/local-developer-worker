from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date
from typing import Any

from .codex_routing import PROFILE_RANK, route_task, validate_codex_policy
from .contracts import canonical_json, result, stable_hash
from .session_log import iter_dated_records
from .telemetry import valid_codex_routing_event_v2


TASK_CLASSES = ("routine_read_or_docs", "bounded_change_or_debug", "cross_cutting_or_high_risk", "ambiguous")
PROFILES = ("efficient", "balanced", "frontier")


REVISION_FIELDS = ("policy_revision", "routing_revision", "alias_revision", "taxonomy_revision")


def _events(payload: dict[str, Any], *, max_age_days: int | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    records, invalid = iter_dated_records(payload.get("journal_root"), date_from=payload.get("date_from"), date_to=payload.get("date_to"))
    rows = [(record, observed_on) for record, observed_on in records if valid_codex_routing_event_v2(record)]
    by_run: dict[tuple[str, str, str, str, str], list[tuple[dict[str, Any], date]]] = defaultdict(list)
    for record, observed_on in rows:
        revision_key = tuple(record[field] for field in REVISION_FIELDS)
        # v2.4 identifies an actual invocation.  Older journal records did
        # not have that capability and retain their conservative run-ID
        # conflict treatment for backward-compatible historical reporting.
        identity = record["execution_id"] if record.get("schema_version") == "2.4.0" else record["run_id"]
        by_run[(identity, *revision_key)].append((record, observed_on))
    events, duplicate_runs, conflicting_runs, stale = [], 0, 0, 0
    today = date.today()
    for run_key in sorted(by_run):
        candidates = by_run[run_key]
        serialized = {canonical_json(record) for record, _ in candidates}
        if len(serialized) > 1:
            conflicting_runs += 1
            continue
        record, observed_on = candidates[0]
        duplicate_runs += len(candidates) - 1
        if max_age_days is not None and not 0 <= (today - observed_on).days <= max_age_days:
            stale += 1
            continue
        normalized = dict(record)
        normalized["task_class"] = record.get("base_task_class", record.get("task_class"))
        normalized["calibration_eligible"] = (
            record["calibration_eligible"]
            if record.get("schema_version") in {"2.3.0", "2.4.0"}
            else record.get("terminal_status") == "pass"
            and record.get("final_verification_status") == "passed"
            and record.get("input_tokens") is not None
            and record.get("output_tokens") is not None
        )
        events.append(normalized)
    return events, {"invalid_records": invalid, "duplicate_attempt_records": duplicate_runs, "conflicting_run_records": conflicting_runs, "stale_records": stale}


def _retention_days(policy: dict[str, Any] | None) -> int | None:
    if policy is None:
        return None
    raw = policy.get("telemetry", {})
    if not isinstance(raw, dict):
        raise ValueError("invalid telemetry configuration")
    days = raw.get("retention_days", 90)
    if not isinstance(days, int) or isinstance(days, bool) or days < 1:
        raise ValueError("invalid telemetry retention")
    return days


def _current_revision(config: dict[str, Any]) -> dict[str, str]:
    return {field: config[field] for field in REVISION_FIELDS}


def _median(values: list[int | float]) -> int | float | None:
    return statistics.median(values) if values else None


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _non_cached_input(event: dict[str, Any]) -> int | None:
    input_tokens, cached_tokens = event.get("input_tokens"), event.get("cached_input_tokens")
    if input_tokens is None or cached_tokens is None:
        return None
    return max(0, input_tokens - cached_tokens)


def _provider_total(event: dict[str, Any]) -> int | None:
    input_tokens, output_tokens = event.get("input_tokens"), event.get("output_tokens")
    if input_tokens is None or output_tokens is None:
        return None
    return input_tokens + output_tokens


def _observed_values(rows: list[dict[str, Any]], getter) -> list[int]:
    values = [getter(row) for row in rows]
    return [value for value in values if value is not None]


def _group(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        groups[(event["task_class"], event["initial_profile"], event["initial_effort"], *(event[field] for field in REVISION_FIELDS))].append(event)
    output = []
    for (task_class, profile, effort, policy_revision, routing_revision, alias_revision, taxonomy_revision), rows in sorted(groups.items()):
        verified = [row for row in rows if row["terminal_status"] == "pass" and row["final_verification_status"] == "passed"]
        first_observed = [row for row in rows if row["first_pass_verification_status"] != "not_observed"]
        output.append({
            "task_class": task_class,
            "initial_profile": profile,
            "initial_effort": effort,
            "revision": {"policy_revision": policy_revision, "routing_revision": routing_revision, "alias_revision": alias_revision, "taxonomy_revision": taxonomy_revision},
            "sample_size": len(rows),
            "verified_sample_size": len(verified),
            "first_pass_verified_success_rate": _rate(sum(row["first_pass_verification_status"] == "passed" for row in first_observed), len(first_observed)),
            "first_pass_observed_count": len(first_observed),
            "escalation_rate": _rate(sum(row["escalation_count"] > 0 for row in rows), len(rows)),
            # An escalation is the only observed under-routing outcome. This is
            # deliberately not a claim about a hypothetical stronger route.
            "under_routing_rate": _rate(sum(row["escalation_count"] > 0 for row in rows), len(rows)),
            "fallback_rate": _rate(sum(row["fallback_count"] > 0 for row in rows), len(rows)),
            "failed_or_blocked_rate": _rate(sum(row["terminal_status"] != "pass" for row in rows), len(rows)),
            "median_input_tokens_per_verified_task": _median(_observed_values(verified, lambda row: row.get("input_tokens"))),
            "median_cached_input_tokens_per_verified_task": _median(_observed_values(verified, lambda row: row.get("cached_input_tokens"))),
            "median_non_cached_input_tokens_per_verified_task": _median(_observed_values(verified, _non_cached_input)),
            "median_output_tokens_per_verified_task": _median(_observed_values(verified, lambda row: row.get("output_tokens"))),
            "median_reasoning_tokens_per_verified_task": _median(_observed_values(verified, lambda row: row.get("reasoning_output_tokens"))),
            "median_provider_total_tokens_per_verified_task": _median(_observed_values(verified, _provider_total)),
            "reasoning_in_output_status": "unknown",
            "median_latency_ms_per_verified_task": _median([row["latency_ms"] for row in verified]),
            "profile_distribution": {item: sum(row["final_profile"] == item for row in rows) for item in PROFILES},
            "effort_distribution": {item: sum(row["final_effort"] == item for row in rows) for item in sorted({row["final_effort"] for row in rows})},
            "over_routing_candidate_rate": 0.0,
        })
    return output


def routing_stats(payload: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = canonical_json(payload)
    try:
        retention_days = _retention_days(policy)
        all_events, diagnostics = _events(payload, max_age_days=retention_days)
        try:
            config = validate_codex_policy(policy) if policy is not None else None
        except ValueError:
            # Generic telemetry reporting must remain available when a minimal
            # policy has no opt-in Codex execution configuration.
            config = None
    except (OSError, ValueError) as exc:
        return result("routing_stats", "session_log", raw, {}, status="invalid_input", errors=[{"code": "invalid_telemetry_range", "detail": str(exc)}])
    events = [event for event in all_events if event["calibration_eligible"]]
    excluded_ineligible = len(all_events) - len(events)
    groups = _group(events)
    mixed = len({tuple(group["revision"].values()) for group in groups}) > 1
    data = {"operational_records": len(all_events), "population_analyzed": len(events), "excluded_ineligible_records": excluded_ineligible, "task_classes": groups, "mixed_revision_population": mixed, **diagnostics}
    if policy is not None:
        data["retention_days"] = retention_days
    if config is not None:
        current = _current_revision(config)
        current_events = [event for event in events if all(event[field] == value for field, value in current.items())]
        data.update({
            "current_revision": current,
            "current_revision_population": len(current_events),
            "excluded_incompatible_records": len(events) - len(current_events),
        })
    return result("routing_stats", "session_log", raw, data, status="partial" if any(diagnostics.values()) else "success")


def _calibration_config(policy: dict[str, Any]) -> dict[str, Any]:
    raw = policy.get("codex", {}).get("calibration", {})
    if not isinstance(raw, dict):
        raise ValueError("invalid calibration configuration")
    values = {
        "enabled": raw.get("enabled", False),
        "min_samples": raw.get("min_samples", 20),
        "strong_sample": raw.get("strong_sample", 50),
        "max_age_days": raw.get("max_age_days", 90),
        "under_routing_escalation_rate": raw.get("under_routing_escalation_rate", 0.35),
        "under_routing_first_pass_rate": raw.get("under_routing_first_pass_rate", 0.8),
        "over_routing_first_pass_rate": raw.get("over_routing_first_pass_rate", 0.95),
    }
    if not isinstance(values["enabled"], bool) or any(not isinstance(values[key], int) or isinstance(values[key], bool) or values[key] < 1 for key in ("min_samples", "strong_sample", "max_age_days")):
        raise ValueError("invalid calibration configuration")
    if values["strong_sample"] < values["min_samples"] or any(not isinstance(values[key], (int, float)) or isinstance(values[key], bool) or not 0 <= values[key] <= 1 for key in ("under_routing_escalation_rate", "under_routing_first_pass_rate", "over_routing_first_pass_rate")):
        raise ValueError("invalid calibration configuration")
    return values


def _replay(events: list[dict[str, Any]], proposals: list[dict[str, Any]]) -> dict[str, Any]:
    affected = [event for proposal in proposals for event in events if event["task_class"] == proposal["task_class"] and event["initial_profile"] == proposal["from_profile"]]
    comparisons = []
    for proposal in proposals:
        rows = [event for event in events if event["task_class"] == proposal["task_class"] and event["initial_profile"] == proposal["from_profile"]]
        comparisons.append({
            "task_class": proposal["task_class"], "current_profile": proposal["from_profile"], "candidate_profile": proposal["to_profile"],
            "observed_escalation_count": sum(event["escalation_count"] for event in rows),
            "observed_final_verification": {status: sum(event["final_verification_status"] == status for event in rows) for status in ("passed", "failed", "uncertain", "not_run")},
            "available_median_provider_total_tokens": _median(_observed_values([event for event in rows if event["terminal_status"] == "pass" and event["final_verification_status"] == "passed"], _provider_total)),
            "reasoning_in_output_status": "unknown",
            "available_median_latency_ms": _median([event["latency_ms"] for event in rows if event["terminal_status"] == "pass"]),
            "counterfactual_outcome": "unverified",
        })
    return {
        "status": "not_run" if not proposals else "completed",
        "population": len(affected),
        "observed_escalations": sum(event["escalation_count"] for event in affected),
        "observed_verified_passes": sum(event["terminal_status"] == "pass" and event["final_verification_status"] == "passed" for event in affected),
        "available_median_latency_ms": _median([event["latency_ms"] for event in affected if event["terminal_status"] == "pass"]),
        "counterfactual_outcome": "unverified",
        "comparisons": comparisons,
    }


def routing_calibrate(payload: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    try:
        config = validate_codex_policy(policy)
        calibration = _calibration_config(policy)
        retention_days = _retention_days(policy)
        if retention_days is not None and retention_days < calibration["max_age_days"]:
            raise ValueError("telemetry retention cannot be shorter than the calibration window")
        operational_events, diagnostics = _events(payload, max_age_days=calibration["max_age_days"])
    except (OSError, ValueError) as exc:
        return result("routing_calibrate", "session_log", raw, {}, status="invalid_input", errors=[{"code": "invalid_calibration_input", "detail": str(exc)}])
    if not calibration["enabled"]:
        eligible = [event for event in operational_events if event["calibration_eligible"]]
        return result("routing_calibrate", "session_log", raw, {"current_policy_revision": config["policy_revision"], "operational_records": len(operational_events), "population_analyzed": len(eligible), "excluded_ineligible_records": len(operational_events) - len(eligible), "verdict": "keep", "reason": "calibration_disabled", "proposed_changes": [], "replay": {"status": "not_run"}, **diagnostics}, status="partial" if any(diagnostics.values()) else "success")
    current_revision = _current_revision(config)
    eligible_events = [event for event in operational_events if event["calibration_eligible"]]
    excluded_ineligible = len(operational_events) - len(eligible_events)
    events = [event for event in eligible_events if all(event[field] == value for field, value in current_revision.items())]
    incompatible = len(eligible_events) - len(events)
    groups = _group(events)
    proposals: list[dict[str, Any]] = []
    for group in groups:
        if group["sample_size"] < calibration["min_samples"]:
            continue
        current = group["initial_profile"]
        # A candidate may never be less restrictive than any observed floor for
        # this class/profile population.
        floor = max((event["deterministic_risk_floor"] for event in events if event["task_class"] == group["task_class"] and event["initial_profile"] == current), key=lambda item: PROFILE_RANK[item])
        if current != "frontier" and ((group["escalation_rate"] or 0) >= calibration["under_routing_escalation_rate"] or (group["first_pass_verified_success_rate"] is not None and group["first_pass_verified_success_rate"] < calibration["under_routing_first_pass_rate"])):
            proposals.append({"kind": "under_routing", "task_class": group["task_class"], "from_profile": current, "to_profile": PROFILES[PROFILE_RANK[current] + 1], "confidence": "eligible" if group["sample_size"] >= calibration["strong_sample"] else "weak", "reason": "observed_escalation_or_first_pass_evidence", "supporting_metrics": group, "expected_benefit": "reduce_observed_escalation_or_first_pass_failure", "risks": ["counterfactual_outcome_unverified", "human_acceptance_required", "risk_floor_preserved"]})
        lower = PROFILES[max(PROFILE_RANK[floor], PROFILE_RANK[current] - 1)]
        lower_evidence = any(event["task_class"] == group["task_class"] and event["initial_profile"] == lower and event["terminal_status"] == "pass" and event["final_verification_status"] == "passed" for event in events)
        if lower != current and lower_evidence and (group["first_pass_verified_success_rate"] or 0) >= calibration["over_routing_first_pass_rate"] and (group["escalation_rate"] or 0) == 0:
            group["over_routing_candidate_rate"] = 1.0
            proposals.append({"kind": "over_routing", "task_class": group["task_class"], "from_profile": current, "to_profile": lower, "confidence": "eligible" if group["sample_size"] >= calibration["strong_sample"] else "weak", "reason": "observed_lower_profile_verified_evidence", "supporting_metrics": group, "expected_benefit": "reduce_profile_cost_subject_to_human_review", "risks": ["counterfactual_outcome_unverified", "human_acceptance_required", "risk_floor_preserved"]})
    verdict = "insufficient-evidence" if len(events) < calibration["min_samples"] else "candidate-change" if proposals else "keep"
    revision = None if not proposals else {
        "revision_id": "CAL-" + stable_hash({"parent": config["policy_revision"], "proposals": proposals, "date_from": payload.get("date_from"), "date_to": payload.get("date_to")})[:16],
        "parent_revision": config["policy_revision"], "reason": "observed_routing_calibration", "evidence_period": {"date_from": payload.get("date_from"), "date_to": payload.get("date_to")},
        "affected_task_classes": sorted({proposal["task_class"] for proposal in proposals}), "thresholds": {key: value for key, value in calibration.items() if key != "enabled"},
        "acceptance_status": "pending_human_acceptance", "rollback_target": config["policy_revision"],
    }
    data = {"current_policy_revision": config["policy_revision"], "current_revision": current_revision, "retention_days": retention_days, "operational_records": len(operational_events), "population_analyzed": len(events), "excluded_ineligible_records": excluded_ineligible, "excluded_incompatible_records": incompatible, "mixed_revision_population": incompatible > 0, "task_classes": groups, "detected_under_routing": [item for item in proposals if item["kind"] == "under_routing"], "detected_over_routing": [item for item in proposals if item["kind"] == "over_routing"], "proposed_changes": proposals, "candidate_revision": revision, "replay": _replay(events, proposals), "verdict": verdict, **diagnostics}
    return result("routing_calibrate", "session_log", raw, data, status="partial" if any(diagnostics.values()) or incompatible else "success")


def routing_explain(payload: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    try:
        allowed = {"task", "task_class", "profile", "policy_path"}
        if set(payload) - allowed:
            raise ValueError("unknown input field")
        config = validate_codex_policy(policy)
        route = route_task(payload.get("task", ""), payload, config)
    except (ValueError, KeyError) as exc:
        return result("routing_explain", "stdin", raw, {}, status="invalid_input", errors=[{"code": "invalid_routing_explain", "detail": str(exc)}])
    return result("routing_explain", "stdin", raw, {"task_class": route.base_task_class, "matched_signals": [route.signal], "routing_disposition": route.routing_disposition, "override_requested_profile": route.override_requested_profile, "override_state": route.override_state, "adaptive_routing": route.adaptive_routing, "uncertainty": route.uncertain, "risk_floor": route.deterministic_risk_floor, "selected_profile": route.profile, "model_alias": route.model_alias, "effort": route.effort, "escalation_path": [route.profile, *[target for source, target in config["escalation"].items() if source == route.profile]], "policy_revision": route.policy_revision})
