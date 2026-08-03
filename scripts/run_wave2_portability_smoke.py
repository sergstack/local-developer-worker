from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from local_developer_worker.contracts import canonical_json


ROOT = Path(__file__).parents[1]


def _git_status(root: Path) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1", "-z"],
        capture_output=True,
        check=True,
    )
    return completed.stdout


def _call(root: Path, policy_path: Path, command: list[str], payload: dict) -> dict:
    completed = subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", *command],
        input=canonical_json({**payload, "policy_path": str(policy_path)}),
        text=True,
        capture_output=True,
        cwd=root,
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LDW_TELEMETRY_DISABLED": "1",
        },
        check=False,
    )
    if not completed.stdout:
        raise RuntimeError(f"no JSON output for {' '.join(command)}")
    return json.loads(completed.stdout)


def _policy(roots: list[Path]) -> str:
    allowed = ", ".join(json.dumps(str(root)) for root in roots)
    return f'''profile = "wave2-read-only-smoke"
network_access = false
automatic_edit = false
automatic_commit = false
automatic_merge = false
production_deploy = false

[automatic]
structured_log_parser = true
test_result_parser = true
git_facts_collector = true
file_inventory = true
context_packer = true
change_summarizer_facts_only = true
semantic_log_clustering = false

[semantic]
enabled = false
code_artifact = "disabled"

[limits]
max_log_size_mb = 20
max_context_files = 20
timeout_seconds = 60

[security]
allowed_repository_roots = [{allowed}]

[fallback]
on_timeout = "codex"
on_invalid_schema = "codex"
on_policy_violation = "codex"
on_internal_error = "codex"
'''


def _target(records: list[dict]) -> str:
    readable = [
        item for item in records
        if item.get("readable") and not item.get("binary") and not item.get("potentially_sensitive")
    ]
    priority = ["pyproject.toml", "README.md", "package.json"]
    by_path = {item["path"]: item for item in readable}
    for path in priority:
        if path in by_path:
            return path
    sources = sorted(item["path"] for item in readable if Path(item["path"]).suffix in {".py", ".js", ".ts", ".rs", ".go"})
    if sources:
        return sources[0]
    if readable:
        return sorted(item["path"] for item in readable)[0]
    raise RuntimeError("no safe readable candidate")


def _bounded_inventory(records: list[dict], target: str) -> list[dict]:
    safe = [
        item for item in records
        if item.get("readable") and not item.get("binary") and not item.get("potentially_sensitive")
    ]
    safe = sorted(safe, key=lambda item: item["path"])
    chosen = safe[:250]
    target_item = next(item for item in safe if item["path"] == target)
    if all(item["path"] != target for item in chosen):
        chosen.append(target_item)
    return [
        {
            "path": item["path"],
            "size_bytes": item.get("size", 0),
            "binary": item.get("binary", False),
            "potentially_sensitive": item.get("potentially_sensitive", False),
            "ignored_by_policy": item.get("ignored_by_policy", False),
            "generated_candidate": item.get("generated_candidate", False),
        }
        for item in chosen
    ]


def _evidence_item(evidence_type: str, value: object, **overrides) -> dict:
    item = {
        "evidence_type": evidence_type,
        "source_tool": overrides.pop("source_tool"),
        "source_run_id": overrides.pop("source_run_id"),
        "source_type": "tool_result",
        "source_path": overrides.pop("source_path", None),
        "event_id": None,
        "test_run_id": None,
        "git_observation_id": None,
        "origin": "observed",
        "value": value,
    }
    item.update(overrides)
    return item


def _smoke(label: str, root: Path, policy_path: Path) -> dict:
    before = _git_status(root)
    git_result = _call(root, policy_path, ["git", "facts"], {"repository_root": str(root)})
    inventory_result = _call(root, policy_path, ["files", "inventory"], {"repository_root": str(root)})
    records = inventory_result["data"]["files"]
    target = _target(records)
    inventory = _bounded_inventory(records, target)
    safe_expansion = next((item["path"] for item in inventory if item["path"] != target), target)
    synthetic_sensitive = {"path": "credentials.wave2.fake", "size_bytes": 0, "potentially_sensitive": True}
    context_result = _call(root, policy_path, ["context", "pack"], {
        "mode": "context",
        "repository_root": str(root),
        "task": f"Read-only portability smoke for {label}",
        "files": inventory + [synthetic_sensitive, {"path": "../neighbor.wave2", "size_bytes": 0}],
        "target_files": [target, "credentials.wave2.fake", "../neighbor.wave2"],
        "max_context_files": 5,
    })
    context_data = context_result["data"]
    expansion_result = _call(root, policy_path, ["context", "pack"], {
        "mode": "expand",
        "repository_root": str(root),
        "previous_run_id": context_result["run_id"],
        "previous_package": context_result,
        "requested_paths": [safe_expansion, "credentials.wave2.fake", "../neighbor.wave2"],
        "reason": "bounded portability expansion",
        "files": inventory + [synthetic_sensitive, {"path": "../neighbor.wave2", "size_bytes": 0}],
        "max_context_files": 5,
    })
    evidence_result = _call(root, policy_path, ["evidence", "build"], {
        "repository_root": str(root),
        "task": f"Read-only portability smoke for {label}",
        "repository_state": git_result["data"],
        "observed_log_events": [],
        "observed_test_results": [],
        "file_inventory": inventory,
        "context_package_reference": {"run_id": context_result["run_id"], "package_hash": context_data["package_hash"]},
        "relevant_files": context_data["included_files"],
        "evidence_items": [
            _evidence_item(
                "context_package",
                {"package_hash": context_data["package_hash"]},
                source_tool="context_packer",
                source_run_id=context_result["run_id"],
                source_path=target,
                origin="deterministic-derived",
            ),
            _evidence_item(
                "file_record",
                {"size_bytes": next(item["size_bytes"] for item in inventory if item["path"] == target)},
                source_tool="file_inventory",
                source_run_id=inventory_result["run_id"],
                source_path=target,
            ),
            _evidence_item(
                "git_state",
                {
                    "working_tree_clean": git_result["data"]["working_tree_clean"],
                    "changed_file_count": len(git_result["data"]["changed_files"]),
                },
                source_tool="git_facts_collector",
                source_run_id=git_result["run_id"],
                git_observation_id=f"GIT-{hashlib.sha256(str(root).encode()).hexdigest()[:12]}",
            ),
        ],
        "constraints": ["read_only", "bounded", "no_sensitive_content"],
        "missing_evidence": ["tests: NOT RUN"],
        "next_bounded_action": "owner review",
    })
    after = _git_status(root)
    included = {item["path"] for item in context_data["included_files"]}
    excluded = {item["path"]: item["reason_code"] for item in context_data["excluded_files"]}
    suffix_counts = Counter(Path(item["path"]).suffix or "no_extension" for item in inventory)
    language_or_type = suffix_counts.most_common(1)[0][0] if suffix_counts else "unknown"
    package = evidence_result["data"]["evidence_package"]
    result = {
        "repository": label,
        "repository_identifier_hash": hashlib.sha256(str(root).encode()).hexdigest(),
        "language_or_type": language_or_type,
        "git_facts_status": git_result["status"],
        "file_inventory_status": inventory_result["status"],
        "context_pack_status": context_result["status"],
        "evidence_build_status": evidence_result["status"],
        "expansion_status": expansion_result["status"],
        "critical_files_found": [target] if target in included else [],
        "critical_files_omitted": [] if target in included else [target],
        "selected_bytes": context_data["metrics"]["selected_bytes"],
        "eligible_input_bytes": context_data["metrics"]["eligible_input_bytes"],
        "context_reduction": context_data["metrics"]["context_reduction"],
        "sensitive_files_included": [path for path in included if "credential" in path.lower()],
        "sensitive_blocked": excluded.get("credentials.wave2.fake") == "sensitive_path",
        "outside_root_reads": [path for path in included if Path(path).is_absolute() or ".." in Path(path).parts],
        "outside_root_blocked": excluded.get("../neighbor.wave2") == "outside_repository_root",
        "source_lineage_complete": package["lineage_complete"],
        "repository_unchanged": before == after,
    }
    result["verdict"] = "pass" if (
        not result["critical_files_omitted"]
        and not result["sensitive_files_included"]
        and not result["outside_root_reads"]
        and result["sensitive_blocked"]
        and result["outside_root_blocked"]
        and result["source_lineage_complete"]
        and result["repository_unchanged"]
    ) else "fail"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run read-only Wave 2 portability smoke checks")
    parser.add_argument("--repository", action="append", required=True, help="LABEL=/absolute/git/root")
    args = parser.parse_args()
    repositories = []
    for value in args.repository:
        label, separator, raw_root = value.partition("=")
        if not separator or not label or not raw_root:
            raise ValueError("repository must use LABEL=/absolute/path")
        root = Path(raw_root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("repository root must be a directory")
        repositories.append((label, root))
    results = []
    with tempfile.TemporaryDirectory(prefix="ldw-wave2-smoke-") as temporary:
        for index, (label, root) in enumerate(repositories, 1):
            policy_path = Path(temporary) / f"policy-{index}.toml"
            policy_path.write_text(_policy([root]))
            try:
                results.append(_smoke(label, root, policy_path))
            except (KeyError, OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
                results.append({
                    "repository": label,
                    "repository_identifier_hash": hashlib.sha256(str(root).encode()).hexdigest(),
                    "verdict": "fail",
                    "error_code": type(exc).__name__,
                })
    output = {
        "schema_version": "1.0.0",
        "status": "pass" if len(results) >= 3 and all(item["verdict"] == "pass" for item in results) else "fail",
        "repository_count": len(results),
        "repositories": results,
    }
    print(canonical_json(output))
    return 0 if output["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
