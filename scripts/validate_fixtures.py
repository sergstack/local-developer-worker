from __future__ import annotations

import json
from pathlib import Path

manifest = Path(__file__).parents[1] / "benchmarks" / "task_manifest.json"
repository_root = manifest.parents[1]
data = json.loads(manifest.read_text())
assert data["schema_version"] == "1.0.0"
assert len(data["cases"]) >= 12
required = {"case_id", "task_class", "input_manifest", "expected_facts", "critical_files", "expected_test_status", "expected_exclusions", "expected_fallback", "expected_output_hash"}
assert all(required <= set(case) for case in data["cases"])
assert len({case["case_id"] for case in data["cases"]}) == len(data["cases"])
classes = {case["task_class"] for case in data["cases"]}
assert classes == {"short_single_file", "multi_file", "log_heavy", "reporting"}
assert all(case["input_manifest"].get("sanitized") is True for case in data["cases"])
assert all(case["files"] and all(isinstance(item.get("size_bytes"), int) and item["size_bytes"] >= 0 for item in case["files"]) for case in data["cases"])
assert all(len(case["files"]) >= 15 for case in data["cases"])
assert all("distractor_files" in case for case in data["cases"])

for case in data["cases"]:
    candidate_paths = [item["path"] for item in case["files"]]
    candidate_set = set(candidate_paths)
    distractors = case["distractor_files"]
    direct_signals = set(case.get("named_files", [])) | set(case.get("changed_files", [])) | set(case.get("failure_files", []))
    imported_signals = {
        target
        for origin, targets in case.get("import_edges", {}).items()
        if origin in direct_signals
        for target in targets
    }
    deterministic_signals = direct_signals | imported_signals
    assert len(candidate_paths) == len(candidate_set)
    assert len(distractors) == len(set(distractors))
    assert set(distractors) <= candidate_set
    assert set(case["critical_files"]) <= candidate_set
    assert set(case["expected_exclusions"]) <= candidate_set
    assert set(distractors).isdisjoint(case["critical_files"])
    assert set(distractors).isdisjoint(deterministic_signals)
    assert set(case["critical_files"]) <= deterministic_signals
    assert len(distractors) * 5 >= len(candidate_paths) * 2
    for item in case["files"]:
        if item.get("potentially_sensitive"):
            assert item["path"] in {".env", "secrets.txt"}
            assert item["path"] in distractors
            continue
        candidate = repository_root / item["path"]
        assert item["path"].split("/", 1)[0] in {"src", "tests", "scripts", "docs", "schemas", "benchmarks"}
        assert candidate.is_file()
        assert item["size_bytes"] == candidate.stat().st_size
print("benchmark manifest valid")
