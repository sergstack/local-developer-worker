from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import median

from local_developer_worker.contracts import canonical_json
from local_developer_worker.tools import context_pack, evidence_build


ROOT = Path(__file__).parents[1]
CORPUS_PATH = ROOT / "fixtures" / "wave2" / "reference_corpus.json"


def _evidence_item(evidence_type: str, value: object, **overrides):
    item = {
        "evidence_type": evidence_type,
        "source_tool": "context_packer",
        "source_run_id": overrides.pop("source_run_id", None),
        "source_type": "tool_result",
        "source_path": overrides.pop("source_path", None),
        "event_id": None,
        "test_run_id": None,
        "git_observation_id": None,
        "origin": "deterministic-derived",
        "value": value,
    }
    item.update(overrides)
    return item


def _context_payload(case: dict, inventory: list[dict], fixture_root: Path) -> dict:
    return {
        "mode": "context",
        "repository_root": str(fixture_root),
        "task": case["task"],
        "files": inventory,
        "target_files": case["explicit_target_files"],
        "target_symbols": case.get("target_symbols", case["required_symbols"]),
        "changed_files": case.get("changed_files", case["expected_git_facts"].get("changed_files", [])),
        "observed_failures": case.get("observed_failures", []),
        "imports": case.get("imports", {}),
        "related_tests": case.get("related_tests", []),
        "constraints": ["bounded", "no_sensitive_content"],
        "max_context_files": 8,
    }


def _evidence_payload(case: dict, context: dict, fixture_root: Path) -> dict:
    items = [
        _evidence_item(
            "context_package",
            {"package_hash": context["data"]["package_hash"]},
            source_run_id=context["run_id"],
            source_path=(case["critical_files"][0] if case["critical_files"] else None),
        )
    ]
    for index, test_path in enumerate(case["required_tests"], 1):
        items.append(_evidence_item(
            "test_status",
            {"status": "unknown"},
            source_tool="test_result_parser",
            source_run_id=f"RUN-tests-{case['case_id']}",
            source_path=test_path,
            test_run_id=f"TEST-{case['case_id']}-{index}",
            origin="observed",
        ))
    if case["expected_git_facts"]:
        items.append(_evidence_item(
            "git_state",
            case["expected_git_facts"],
            source_tool="git_facts_collector",
            source_run_id=f"RUN-git-{case['case_id']}",
            git_observation_id=f"GIT-{case['case_id']}",
            origin="observed",
        ))
    for index, failure in enumerate(case["expected_observed_failures"], 1):
        items.append(_evidence_item(
            "log_event",
            {"status": "observed_failure"},
            source_tool="structured_log_parser",
            source_run_id=f"RUN-log-{case['case_id']}",
            source_path=failure,
            event_id=f"EV-{index:06d}",
            origin="observed",
        ))
    return {
        "repository_root": str(fixture_root),
        "task": case["task"],
        "repository_state": case["expected_git_facts"],
        "observed_log_events": [],
        "observed_test_results": [],
        "file_inventory": context["data"]["included_files"] + context["data"]["excluded_files"],
        "context_package_reference": {"run_id": context["run_id"], "package_hash": context["data"]["package_hash"]},
        "relevant_files": context["data"]["included_files"],
        "evidence_items": items,
        "current_observed_state": "bounded evidence captured",
        "constraints": ["bounded", "no_sensitive_content"],
        "missing_evidence": ([] if case["required_tests"] else ["tests: NOT RUN"]),
        "next_bounded_action": "request expansion if critical context is missing",
    }


def evaluate() -> dict:
    corpus = json.loads(CORPUS_PATH.read_text())
    fixture_root = ROOT / corpus["repository_fixture_or_root"]
    inventory = corpus["inventory"]
    inventory_paths = {item["path"] for item in inventory}
    inventory_by_path = {item["path"]: item for item in inventory}
    case_results = []
    reductions = []
    critical_omissions = 0
    sensitive_leaks = 0
    outside_root_reads = 0
    silent_exclusions = 0
    traced_inclusions = 0
    total_inclusions = 0
    visible_exclusions = 0
    total_exclusions = 0
    safe_expansion_total = 0
    safe_expansion_success = 0
    sensitive_expansion_total = 0
    sensitive_expansion_blocked = 0
    outside_expansion_total = 0
    outside_expansion_blocked = 0
    linkage_success = 0
    lineage_complete = 0
    deterministic_cases = 0

    for case in corpus["cases"]:
        payload = _context_payload(case, inventory, fixture_root)
        first = context_pack(payload)
        second = context_pack(payload)
        deterministic = first == second
        deterministic_cases += int(deterministic)
        data = first["data"]
        included = {item["path"] for item in data["included_files"]}
        excluded = {item["path"] for item in data["excluded_files"]}
        omissions = sorted(set(case["critical_files"]) - included)
        critical_omissions += len(omissions)
        sensitive_included = sorted(included & set(case["forbidden_sensitive_files"]))
        sensitive_leaks += len(sensitive_included)
        outside_included = sorted(path for path in included if Path(path).is_absolute() or ".." in Path(path).parts)
        outside_root_reads += len(outside_included)
        accounted = (included | excluded) & inventory_paths
        missing_accounting = sorted(inventory_paths - accounted)
        silent_exclusions += len(missing_accounting)
        total_inclusions += len(data["included_files"])
        traced_inclusions += sum(
            bool(item.get("selection_reason") and item.get("evidence_source") and item.get("relevance_status"))
            for item in data["included_files"]
        )
        total_exclusions += len(data["excluded_files"])
        visible_exclusions += sum(bool(item.get("reason_code") and item.get("policy_rule")) for item in data["excluded_files"])
        if case.get("eligible_for_reduction") and data["metrics"]["context_reduction"] is not None:
            reductions.append(data["metrics"]["context_reduction"])

        expansion = context_pack({
            "mode": "expand",
            "repository_root": str(fixture_root),
            "previous_run_id": first["run_id"],
            "previous_package": first,
            "requested_paths": case["expansion_requests"],
            "requested_symbols": case["required_symbols"],
            "reason": "frozen acceptance request",
            "files": inventory,
            "max_context_files": 8,
        })
        expansion_data = expansion["data"]
        linkage_success += int(expansion_data.get("previous_run_id") == first["run_id"])
        added_or_existing = {item["path"] for item in expansion_data.get("added_files", [])} | included
        expansion_excluded = {item["path"]: item["reason_code"] for item in expansion_data.get("still_excluded", [])}
        for requested in case["expansion_requests"]:
            item = inventory_by_path.get(requested)
            if item and (item.get("potentially_sensitive") or "credential" in requested.lower()):
                sensitive_expansion_total += 1
                sensitive_expansion_blocked += int(expansion_excluded.get(requested) == "sensitive_path")
            elif Path(requested).is_absolute() or ".." in Path(requested).parts:
                outside_expansion_total += 1
                outside_expansion_blocked += int(expansion_excluded.get(requested) == "outside_repository_root")
            elif item and not item.get("binary") and not item.get("ignored_by_policy"):
                safe_expansion_total += 1
                safe_expansion_success += int(requested in added_or_existing)

        evidence = evidence_build(_evidence_payload(case, first, fixture_root))
        package = evidence["data"]["evidence_package"]
        lineage_complete += int(package["lineage_complete"])
        resume = package["resume_state"]
        resume_complete = all(key in resume for key in (
            "objective", "current_observed_state", "files_already_considered", "tests_actually_observed",
            "known_failures", "constraints", "missing_evidence", "next_bounded_action",
        ))
        case_results.append({
            "case_id": case["case_id"],
            "context_status": first["status"],
            "selection_status": data["selection_status"],
            "critical_omissions": omissions,
            "sensitive_included": sensitive_included,
            "outside_root_reads": outside_included,
            "silent_exclusions": missing_accounting,
            "context_reduction": data["metrics"]["context_reduction"],
            "expansion_status": expansion["status"],
            "lineage_complete": package["lineage_complete"],
            "resume_complete": resume_complete,
            "deterministic": deterministic,
        })

    median_reduction = median(reductions) if reductions else None
    reduction_at_least_25_rate = (
        sum(value >= 0.25 for value in reductions) / len(reductions) if reductions else None
    )
    metrics = {
        "case_count": len(case_results),
        "eligible_reduction_case_count": len(reductions),
        "critical_file_omissions": critical_omissions,
        "sensitive_file_leaks": sensitive_leaks,
        "outside_root_reads": outside_root_reads,
        "silent_exclusions": silent_exclusions,
        "included_traceability": traced_inclusions / total_inclusions if total_inclusions else 1.0,
        "excluded_visibility": visible_exclusions / total_exclusions if total_exclusions else 1.0,
        "median_context_reduction": median_reduction,
        "reduction_at_least_0_25_rate": reduction_at_least_25_rate,
        "safe_expansion_success_rate": safe_expansion_success / safe_expansion_total if safe_expansion_total else 1.0,
        "sensitive_expansion_block_rate": sensitive_expansion_blocked / sensitive_expansion_total if sensitive_expansion_total else 1.0,
        "outside_expansion_block_rate": outside_expansion_blocked / outside_expansion_total if outside_expansion_total else 1.0,
        "previous_package_linkage_rate": linkage_success / len(case_results),
        "evidence_lineage_complete_rate": lineage_complete / len(case_results),
        "deterministic_case_rate": deterministic_cases / len(case_results),
        "raw_repository_reread_rate": "NOT MEASURED",
        "time_to_actionable_context": "NOT MEASURED",
        "resume_success_rate": sum(case["resume_complete"] for case in case_results) / len(case_results),
    }
    gates = {
        "reference_cases": metrics["case_count"] >= 15,
        "critical_omissions_zero": critical_omissions == 0,
        "sensitive_leaks_zero": sensitive_leaks == 0,
        "outside_root_reads_zero": outside_root_reads == 0,
        "silent_exclusions_zero": silent_exclusions == 0,
        "included_traceability_complete": metrics["included_traceability"] == 1.0,
        "excluded_visibility_complete": metrics["excluded_visibility"] == 1.0,
        "median_context_reduction": median_reduction is not None and median_reduction >= 0.40,
        "reduction_case_rate": reduction_at_least_25_rate is not None and reduction_at_least_25_rate >= 0.80,
        "safe_expansion_complete": metrics["safe_expansion_success_rate"] == 1.0,
        "sensitive_expansion_blocked": metrics["sensitive_expansion_block_rate"] == 1.0,
        "outside_expansion_blocked": metrics["outside_expansion_block_rate"] == 1.0,
        "previous_package_linkage_complete": metrics["previous_package_linkage_rate"] == 1.0,
        "evidence_lineage_complete": metrics["evidence_lineage_complete_rate"] == 1.0,
        "resume_complete": metrics["resume_success_rate"] == 1.0,
        "deterministic": metrics["deterministic_case_rate"] == 1.0,
    }
    return {
        "schema_version": "1.0.0",
        "gate_status": "INFORMATIONAL_ONLY",
        "corpus_sha256": hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest(),
        "status": "pass" if all(gates.values()) else "fail",
        "metrics": metrics,
        "gates": gates,
        "cases": case_results,
    }


if __name__ == "__main__":
    print(canonical_json(evaluate()))
