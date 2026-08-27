from __future__ import annotations

import hashlib
import json
from pathlib import Path

from local_developer_worker.contracts import canonical_json
from local_developer_worker.tools import context_pack


ROOT = Path(__file__).parents[1]
MANIFEST_PATH = ROOT / "benchmarks" / "context_overlap_manifest.json"


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    rows = []
    for case in manifest["cases"]:
        output = context_pack({"repository_root": str(ROOT), "files": case["files"], "target_files": case.get("target_files", []), "changed_files": case.get("changed_files", [])})["data"]
        selected = {item["path"] for item in output["included_files"]}
        critical = set(case["critical_files"])
        candidate_bytes = sum(item["size_bytes"] for item in case["files"])
        selected_bytes = sum(item["size_bytes"] for item in case["files"] if item["path"] in selected)
        rows.append({"case_id": case["case_id"], "critical_recall": len(selected & critical) / len(critical), "candidate_bytes": candidate_bytes, "selected_bytes": selected_bytes, "context_reduction": round((candidate_bytes - selected_bytes) / candidate_bytes, 4), "redundant_content_exclusions": [item for item in output["excluded_files"] if item["reason_code"] == "redundant_content"]})
    print(canonical_json({"measurement_contract_version": "1.1.0", "baseline_reference": manifest["baseline_reference"], "corpus_path": "benchmarks/context_overlap_manifest.json", "corpus_sha256": hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), "cases": rows}))


if __name__ == "__main__":
    main()
