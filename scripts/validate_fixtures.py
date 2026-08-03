from __future__ import annotations

import json
import re
from hashlib import sha256
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

stage_b_root = repository_root / "fixtures" / "stage_b"
reference = json.loads((stage_b_root / "reference_events.json").read_text())
ground_truth = json.loads((stage_b_root / "expected_groups.json").read_text())
events = reference["events"]
event_ids = [event["event_id"] for event in events]
allowed_event_fields = {
    "event_id", "level", "component", "message", "exception_type", "source_file", "source_line",
    "raw_line_start", "raw_line_end", "raw_hash", "parse_status", "origin",
}
assert reference["schema_version"] == ground_truth["schema_version"] == "1.0.0"
assert len(events) >= 30
assert len(event_ids) == len(set(event_ids))
assert all(set(event) == allowed_event_fields for event in events)
assert all(re.fullmatch(r"EV-\d{6}", event["event_id"]) for event in events)
assert all(event["origin"] == "observed" and event["parse_status"] == "parsed" for event in events)
assert all(event["raw_hash"] == sha256(event["message"].encode()).hexdigest() for event in events)
assert all(not Path(event["source_file"]).is_absolute() and ".." not in Path(event["source_file"]).parts for event in events)
assert not any(re.search(r"(?:AKIA[0-9A-Z]{16}|-----BEGIN .*PRIVATE KEY-----|password\s*[:=]|token\s*[:=])", event["message"], re.I) for event in events)

groups = ground_truth["groups"]
group_ids = [group["group_id"] for group in groups]
grouped_ids = [event_id for group in groups for event_id in group["members"]]
excluded_ids = [row["event_id"] for row in ground_truth["excluded"]]
assert len(group_ids) == len(set(group_ids))
assert all(len(group["members"]) >= 2 for group in groups)
assert len(grouped_ids) == len(set(grouped_ids))
assert len(excluded_ids) == len(set(excluded_ids))
assert set(grouped_ids).isdisjoint(excluded_ids)
assert set(grouped_ids) | set(excluded_ids) == set(event_ids)
membership = {event_id: group["group_id"] for group in groups for event_id in group["members"]}
for left, right in ground_truth["must_remain_separate"]:
    assert left in event_ids and right in event_ids
    assert membership.get(left) != membership.get(right)

print(f"benchmark manifest and Stage B reference fixtures valid ({len(events)} reference events)")
