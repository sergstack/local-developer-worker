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

live_evidence = json.loads((stage_b_root / "phase_2_live_run_evidence.json").read_text())
assert live_evidence["schema_version"] == "1.0.0"
assert live_evidence["classification"] == "OBSERVED"
assert live_evidence["model_response_observed"] is True
assert live_evidence["raw_response_stored"] is False
assert live_evidence["code_artifact"] == "disabled"
assert live_evidence["mutation_capabilities_granted"] is False
assert re.fullmatch(r"[0-9a-f]{64}", live_evidence["stdout_sha256"])

wave2 = json.loads((repository_root / "fixtures" / "wave2" / "reference_corpus.json").read_text())
wave2_required = {
    "case_id", "repository_fixture_or_root", "task", "explicit_target_files", "critical_files",
    "allowed_related_files", "acceptable_exclusions", "forbidden_sensitive_files", "required_symbols",
    "required_tests", "expected_git_facts", "expected_observed_failures", "expansion_requests",
    "source_type", "sensitive_content_present",
}
assert wave2["schema_version"] == "1.0.0"
assert wave2["frozen"] is True
assert len(wave2["cases"]) == 15
assert len({case["case_id"] for case in wave2["cases"]}) == 15
assert all(wave2_required <= set(case) for case in wave2["cases"])
assert all(case["source_type"] in {"real_repository", "sanitized_fixture"} for case in wave2["cases"])
assert all(case["sensitive_content_present"] is False for case in wave2["cases"])
assert all(set(case["critical_files"]).isdisjoint(case["forbidden_sensitive_files"]) for case in wave2["cases"])

pb4_corpus = json.loads((stage_b_root / "pb4_v2_cases.json").read_text())
assert pb4_corpus["corpus_id"] == "PB4-03-FROZEN-V1"
assert len(pb4_corpus["cases"]) == 5
assert len({case["case_id"] for case in pb4_corpus["cases"]}) == 5
for case in pb4_corpus["cases"]:
    assert case["fixture_hash"] == sha256(case["text"].encode()).hexdigest()
    assert case["observed_event_count"] > 0
    assert case["sensitive_content_present"] is False
    expected_ids = [event_id for rows in case["expected_dispositions"].values() for event_id in rows]
    assert len(expected_ids) == case["observed_event_count"]
    assert len(expected_ids) == len(set(expected_ids))
    assert all(left in expected_ids and right in expected_ids for pair in case["required_group_pairs"] + case["forbidden_merge_pairs"] for left, right in [pair])

pb4_compile = json.loads((stage_b_root / "pb4_compile_error_evidence.json").read_text())
compile_case = next(case for case in pb4_corpus["cases"] if case["case_id"] == "PB4-COMPILE-ERROR")
assert pb4_compile["source_hash"] == "6bb4ada224b838e8737b36fc8a2367350b05e0233fa76fe263576ade5cf70791"
assert pb4_compile["sanitized_fixture_hash"] == compile_case["fixture_hash"]
assert pb4_compile["observed_events"] == {"total": 6, "parsed": 1, "unknown_event": 4, "part_of_event": 1}
assert pb4_compile["v1_result"] == {"accepted": False, "failure_class": "source_span_recall_failed", "omitted_event_ids": ["EV-000006"]}
assert pb4_compile["raw_provider_response_stored"] is False

pb4_evidence = json.loads((stage_b_root / "pb4_03_evaluation_evidence.json").read_text())
assert pb4_evidence["corpus_id"] == pb4_corpus["corpus_id"]
assert pb4_evidence["corpus_file_sha256"] == sha256((stage_b_root / "pb4_v2_cases.json").read_bytes()).hexdigest()
assert pb4_evidence["raw_provider_response_stored"] is False
assert set(pb4_evidence["case_results"]) == {"v1", "v2", "fallback"}
assert all(len(rows) == 5 for rows in pb4_evidence["case_results"].values())
assert all(row["stage_a_events_match_frozen_input"] is True for rows in pb4_evidence["case_results"].values() for row in rows)

pb4_mac = json.loads((stage_b_root / "pb4_03_mac_evaluation_evidence.json").read_text())
assert pb4_mac["execution_status"] == "COMPLETE"
assert pb4_mac["contract_version"] == 2
assert pb4_mac["endpoint"] == "http://127.0.0.1:11435/api/generate"
assert pb4_mac["models"] == ["qwen3:4b", "gemma3:4b", "ibm/granite4.1:8b", "qwen3:8b"]
assert pb4_mac["expected_runs"] == pb4_mac["attempted_runs"] == pb4_mac["valid_runs"] == 20
assert pb4_mac["invalid_runs"] == pb4_mac["infrastructure_retries"] == 0
assert pb4_mac["listener"]["verified"] is True and pb4_mac["listener"]["physical_host"] == "Mac"
assert pb4_mac["listener"]["process"] == "ollama" and pb4_mac["listener"]["is_tunnel_or_proxy"] is False
assert pb4_mac["corpus_before"] == pb4_mac["corpus_after"] and pb4_mac["corpus_unchanged"] is True
assert pb4_mac["corpus_before"]["manifest_hash"] == sha256((stage_b_root / "pb4_v2_cases.json").read_bytes()).hexdigest()
assert all(run["preflight"] == {"tags_checked": True, "exact_tag_present": True} for run in pb4_mac["runs"])
assert all(run["model_requested"] == run["model_reported"] for run in pb4_mac["runs"])
assert all(run["endpoint"] == pb4_mac["endpoint"] and run["listener_verified"] is True for run in pb4_mac["runs"])
assert all(run["accounting"]["fully_accounted"] is True and run["safety"]["raw_response_stored"] is False and run["safety"]["endpoint_fallback_used"] is False for run in pb4_mac["runs"])
assert all(row["invented_accepted_id_count"] == row["duplicate_accepted_id_count"] == row["omitted_accepted_candidate_id_count"] == 0 and row["fallback_coverage_rate"] == 1.0 for row in pb4_mac["per_model"])
assert pb4_mac["comparison"]["winner"] == "NOT ESTABLISHED"
assert pb4_mac["safety"] == {"physical_execution_host": "Mac", "external_internet_inference_observed": False, "raw_provider_response_stored": False, "endpoint_fallback_used": False, "model_pull_performed": False}

print(f"benchmark manifest, {len(events)} Stage B reference events, and {len(wave2['cases'])} frozen Wave 2 cases valid")
