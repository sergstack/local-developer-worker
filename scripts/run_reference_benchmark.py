from __future__ import annotations

import json
import hashlib
import statistics
import subprocess
import time
from collections import defaultdict
from pathlib import Path

from local_developer_worker.contracts import canonical_json
from local_developer_worker.contracts import valid_tool_result
from local_developer_worker.tools import context_pack


ROOT = Path(__file__).parents[1]
MANIFEST_PATH = ROOT / "benchmarks" / "task_manifest.json"
MEASUREMENT_CONTRACT_VERSION = "1.0.0"
BASELINE_ID = "context-efficiency-vnext-issue-23"


def token_proxy(byte_count: int) -> int:
    """Deterministic byte-based proxy; it is not a measured Codex token count."""
    return (byte_count + 3) // 4


def reduction_percent(task_bytes: int, files: list[dict], included_paths: set[str], distractor_files: set[str], distractor_scale: float = 1.0) -> float:
    def size(item: dict) -> float:
        scale = distractor_scale if item["path"] in distractor_files else 1.0
        return item["size_bytes"] * scale

    baseline = task_bytes + sum(size(item) for item in files)
    selected = task_bytes + sum(size(item) for item in files if item["path"] in included_paths)
    return round((baseline - selected) * 100 / baseline, 4) if baseline else 0.0


def summarize(values: list[float | int]) -> dict:
    return {
        "n": len(values),
        "raw_values": values,
        "min": min(values),
        "max": max(values),
        "median": round(statistics.median(values), 4),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_revision() -> dict[str, str]:
    try:
        git_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        working_tree_state = "dirty" if subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=False
        ).stdout else "clean"
    except (OSError, subprocess.CalledProcessError):
        git_commit = "0" * 40
        working_tree_state = "unknown"
    return {"git_commit": git_commit, "working_tree_state": working_tree_state, "runner_sha256": _sha256(Path(__file__))}


def _metric(status: str, unit: str, value: int | float | None, method: str | None = None) -> dict:
    metric = {"status": status, "unit": unit, "value": value}
    if method is not None:
        metric["method"] = method
    return metric


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    rows = []
    for case in manifest["cases"]:
        payload = {key: case[key] for key in ("files", "named_files", "changed_files", "failure_files", "import_edges") if key in case}
        started = time.perf_counter()
        audit = context_pack({**payload, "mode": "audit"})
        context = context_pack({**payload, "mode": "context", "task": case["case_id"], "test_status": case["expected_test_status"], "missing_checks": [], "evidence_references": []})
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        task_bytes = len(case["raw_context"].encode())
        candidate_bytes = sum(item["size_bytes"] for item in case["files"])
        included_paths = set(context["data"]["relevant_files"])
        distractor_files = set(case["distractor_files"])
        selected_bytes = sum(item["size_bytes"] for item in case["files"] if item["path"] in included_paths)
        critical_omissions = sorted(set(case["critical_files"]) - included_paths)
        unexpected_inclusions = sorted(set(case["expected_exclusions"]) & included_paths)
        audit_bytes = len(canonical_json(audit).encode())
        projection_bytes = len(canonical_json(context).encode())
        baseline_bytes = task_bytes + candidate_bytes
        minimal_context_bytes = task_bytes + selected_bytes
        excluded_file_count = len(case["files"]) - len(included_paths)
        critical_files = set(case["critical_files"])
        rejected_distractors = distractor_files - included_paths
        context_reduction_percent = reduction_percent(task_bytes, case["files"], included_paths, distractor_files)
        rows.append({"case_id": case["case_id"], "task_class": case["task_class"], "task_bytes": task_bytes, "candidate_file_bytes": candidate_bytes, "codex_only_input_bytes": baseline_bytes, "minimal_audit_protocol_bytes": audit_bytes, "minimal_context_projection_bytes": projection_bytes, "minimal_context_bytes": minimal_context_bytes, "context_reduction_bytes": baseline_bytes - minimal_context_bytes, "context_reduction_percent": context_reduction_percent, "excluded_file_bytes": candidate_bytes - selected_bytes, "excluded_file_count": excluded_file_count, "excluded_file_ratio": round(excluded_file_count / len(case["files"]), 4), "critical_recall": round(len(critical_files & included_paths) / len(critical_files), 4) if critical_files else 1.0, "distractor_rejection_rate": round(len(rejected_distractors) / len(distractor_files), 4) if distractor_files else 1.0, "sensitivity_context_reduction_percent": {"x0.1": reduction_percent(task_bytes, case["files"], included_paths, distractor_files, 0.1), "x10": reduction_percent(task_bytes, case["files"], included_paths, distractor_files, 10.0)}, "token_proxy_before": token_proxy(baseline_bytes), "token_proxy_after": token_proxy(minimal_context_bytes), "token_proxy_saving": token_proxy(baseline_bytes) - token_proxy(minimal_context_bytes), "worker_latency_ms": latency_ms, "schema_validity": "OBSERVED" if valid_tool_result(audit) and valid_tool_result(context) else "FAILED", "fallback": "NOT RUN", "review_time": "NOT RUN", "rejected_results": "NOT RUN", "critical_omissions": critical_omissions, "unexpected_inclusions": unexpected_inclusions, "metrics": {"candidate_context_bytes": _metric("observed", "bytes", candidate_bytes, "sum of fixed corpus candidate sizes"), "selected_context_bytes": _metric("observed", "bytes", selected_bytes, "sum of selected fixed corpus candidate sizes"), "estimated_input_tokens_before": _metric("estimated", "tokens", token_proxy(baseline_bytes), "ceil(bytes / 4); not a provider token count"), "estimated_input_tokens_after": _metric("estimated", "tokens", token_proxy(minimal_context_bytes), "ceil(bytes / 4); not a provider token count"), "files_considered": _metric("observed", "files", len(case["files"]), "fixed corpus candidate list"), "files_selected": _metric("observed", "files", len(included_paths), "context pack output"), "context_expansions": _metric("observed", "expansions", 0, "baseline invokes no expand mode"), "coding_agent_tool_calls": _metric("not_measured", "calls", None), "task_latency_ms": _metric("observed", "milliseconds", latency_ms, "offline audit and context-pack wall-clock duration"), "task_success": _metric("not_measured", "boolean", None), "provider_tokens": _metric("unavailable", "tokens", None), "provider_cost": _metric("unavailable", "currency", None)}})

    grouped = defaultdict(list)
    for row in rows:
        grouped[row["task_class"]].append(row)
    class_results = {}
    for task_class, class_rows in sorted(grouped.items()):
        base = summarize([row["context_reduction_percent"] for row in class_rows])
        sensitivity = {}
        size_sensitive = False
        for scale in ("x0.1", "x10"):
            scaled = summarize([row["sensitivity_context_reduction_percent"][scale] for row in class_rows])
            delta = round(abs(scaled["median"] - base["median"]), 4)
            sensitivity[scale] = {**scaled, "median_delta_percentage_points": delta}
            size_sensitive = size_sensitive or delta > 10
        flags = []
        if base["n"] < 5:
            flags.append("LOW_N")
        if size_sensitive:
            flags.append("SIZE_SENSITIVE")
        class_results[task_class] = {
            **base,
            "flags": flags,
            "economic_promotion_eligible": not size_sensitive,
            "sensitivity": sensitivity,
            "selection_metrics": {
                name: summarize([row[name] for row in class_rows])
                for name in ("excluded_file_count", "excluded_file_ratio", "critical_recall", "distractor_rejection_rate")
            },
        }
    output = {"measurement_contract_version": MEASUREMENT_CONTRACT_VERSION, "baseline_id": BASELINE_ID, "source_revision": _source_revision(), "corpus": {"manifest_path": "benchmarks/task_manifest.json", "manifest_sha256": _sha256(MANIFEST_PATH), "case_count": len(rows)}, "measurement_status": "observed", "status": "OBSERVED", "gate_status": "INFORMATIONAL_ONLY", "measurement": "Baseline assumes the agent fully reads every candidate file, so reported context reduction is an upper bound on savings; a real agent may inspect candidates selectively. Minimal context is task bytes plus selected-file bytes. Protocol envelopes are reported separately. TOKEN PROXY uses bytes/4; no Codex token usage was measured. Results are not used for promotion decisions.", "case_count": len(rows), "class_results": class_results, "cases": rows}
    print(canonical_json(output))


if __name__ == "__main__":
    main()
