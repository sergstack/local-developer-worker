from __future__ import annotations

import argparse
import inspect
import json
import re
import statistics
import subprocess
import time
import urllib.request
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from local_developer_worker.contracts import canonical_json
from local_developer_worker.log_process import log_process
from local_developer_worker.stage_b_accounting import initial_dispositions, validate_v2_candidate
from local_developer_worker.stage_b_cluster import V2_CANDIDATE_RESPONSE_SCHEMA
from local_developer_worker.tools import parse_log


MAC_ENDPOINT = "http://127.0.0.1:11435/api/generate"
REQUIRED_MODELS = ("qwen3:4b", "gemma3:4b", "ibm/granite4.1:8b", "qwen3:8b")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run frozen PB4-03 v2 evaluation on an explicitly selected Mac-local Ollama endpoint.")
    parser.add_argument("--contract-version", type=int, choices=(2,), required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", action="append", required=True, dest="models")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def validate_cli(args: argparse.Namespace) -> None:
    if args.endpoint != MAC_ENDPOINT:
        raise ValueError("mac_endpoint_must_be_explicit_127_0_0_1_11435")
    if len(args.models) != len(set(args.models)):
        raise ValueError("duplicate_model_argument")
    if any(model not in REQUIRED_MODELS for model in args.models):
        raise ValueError("unexpected_model_tag")


def _hash(value: Any) -> str:
    return sha256(canonical_json(value).encode()).hexdigest()


def corpus_snapshot(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    corpus = json.loads(raw)
    cases = corpus.get("cases")
    if not isinstance(cases, list) or len(cases) != 5:
        raise ValueError("frozen_corpus_must_have_five_cases")
    records = []
    accounting = []
    for case in cases:
        fixture_hash = sha256(case["text"].encode()).hexdigest()
        if fixture_hash != case["fixture_hash"]:
            raise ValueError("frozen_fixture_hash_mismatch")
        records.append({"case_id": case["case_id"], "fixture_hash": fixture_hash, "observed_event_count": case["observed_event_count"]})
        accounting.append({"case_id": case["case_id"], "observed_event_count": case["observed_event_count"], "expected_dispositions": case["expected_dispositions"], "required_group_pairs": case["required_group_pairs"], "forbidden_merge_pairs": case["forbidden_merge_pairs"]})
    return {"manifest_hash": sha256(raw).hexdigest(), "case_count": len(cases), "cases": records, "expected_accounting_metadata_hash": _hash(accounting)}


def load_corpus(path: Path) -> dict[str, Any]:
    corpus = json.loads(path.read_text())
    for case in corpus["cases"]:
        events = parse_log({"text": case["text"], "source": case["case_id"]})["data"]["events"]
        actual: dict[str, list[str]] = {}
        for row in initial_dispositions(events):
            actual.setdefault(row["disposition"], []).append(row["event_id"])
        if len(events) != case["observed_event_count"] or actual != case["expected_dispositions"]:
            raise ValueError("frozen_accounting_metadata_mismatch")
    return corpus


def verify_listener() -> dict[str, Any]:
    completed = subprocess.run(["lsof", "-nP", "-iTCP:11435", "-sTCP:LISTEN"], capture_output=True, text=True, check=False)
    lines = [line for line in completed.stdout.splitlines() if "127.0.0.1:11435" in line and "LISTEN" in line]
    if completed.returncode or len(lines) != 1:
        raise ValueError("mac_local_listener_not_verified")
    fields = lines[0].split()
    process, pid_text = fields[0], fields[1]
    if process.lower() != "ollama" or not pid_text.isdigit():
        raise ValueError("mac_local_listener_not_verified")
    process_row = subprocess.run(["ps", "-p", pid_text, "-o", "comm="], capture_output=True, text=True, check=False)
    executable = process_row.stdout.strip()
    if process_row.returncode or not executable or any(token in executable.lower() for token in ("ssh", "socat", "proxy", "tunnel")) or "ollama" not in executable.lower():
        raise ValueError("mac_local_listener_not_verified")
    return {"address": "127.0.0.1", "port": 11435, "pid": int(pid_text), "process": "ollama", "executable": executable, "process_class": "local_ollama_service", "physical_host": "Mac", "is_tunnel_or_proxy": False, "verified": True}


def _tags_url() -> str:
    return "http://127.0.0.1:11435/api/tags"


def exact_tags() -> set[str]:
    completed = subprocess.run(["curl", "--fail", "--silent", "--show-error", _tags_url()], capture_output=True, text=True, check=False)
    if completed.returncode:
        raise OSError("mac_tags_preflight_failed")
    envelope = json.loads(completed.stdout)
    return {row["name"] for row in envelope.get("models", []) if isinstance(row, dict) and isinstance(row.get("name"), str)}


class ObservedTransport:
    def __init__(self, requested_model: str):
        self.requested_model = requested_model
        self.record: dict[str, Any] = {"tags_checked": False, "exact_tag_present": False, "attempted": False, "succeeded": False, "timeout": False, "latency_ms": None, "model_reported": None, "response_identity_match": False, "candidate_returned": False, "prompt_hash": None, "schema_hash": None, "options_hash": None}
        self.candidate: dict[str, Any] | None = None

    def __call__(self, endpoint: str, request_payload: dict[str, Any]) -> dict[str, Any]:
        tags = exact_tags()
        self.record["tags_checked"] = True
        self.record["exact_tag_present"] = self.requested_model in tags
        if not self.record["exact_tag_present"]:
            raise ValueError("required_mac_model_missing")
        if endpoint != MAC_ENDPOINT or request_payload.get("model") != self.requested_model:
            raise ValueError("explicit_endpoint_or_model_changed")
        self.record["attempted"] = True
        self.record["prompt_hash"] = sha256(request_payload["prompt"].encode()).hexdigest()
        self.record["schema_hash"] = _hash(request_payload["format"])
        self.record["options_hash"] = _hash({key: request_payload[key] for key in ("stream", "think", "options")})
        request = urllib.request.Request(endpoint, data=canonical_json(request_payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
        started = time.perf_counter()
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=120) as response:
                body = response.read(1_000_001)
        except TimeoutError:
            self.record["timeout"] = True
            raise
        finally:
            self.record["latency_ms"] = round((time.perf_counter() - started) * 1000)
        if len(body) > 1_000_000:
            raise ValueError("model_response_too_large")
        envelope = json.loads(body)
        self.record["model_reported"] = envelope.get("model")
        self.record["response_identity_match"] = self.record["model_reported"] == self.requested_model
        if not self.record["response_identity_match"]:
            raise ValueError("response_model_identity_mismatch")
        candidate = json.loads(envelope["response"])
        if not isinstance(candidate, dict):
            raise ValueError("invalid_model_response")
        self.record["succeeded"] = True
        self.record["candidate_returned"] = True
        self.candidate = {key: candidate.get(key) for key in ("contract_version", "groups", "ungrouped_candidate_ids")}
        return candidate


def active_policy(model: str, endpoint: str) -> dict[str, Any]:
    return {"automatic": {"semantic_log_clustering": True}, "semantic": {"enabled": True, "code_artifact": "disabled", "model": model, "endpoint": endpoint, "routing_event_threshold": 1, "catchall_group_share": 0.8, "unclassified_observed_threshold": 0}, "limits": {"timeout_seconds": 120}}


def _group_members(groups: list[dict[str, Any]]) -> list[list[str]]:
    return [list(group.get("source_span", [])) for group in groups]


def _same_group(groups: list[list[str]], left: str, right: str) -> bool:
    return any(left in group and right in group for group in groups)


def semantic_quality(case: dict[str, Any], groups: list[dict[str, Any]], accepted: bool) -> dict[str, Any]:
    members = _group_members(groups)
    false_merges = sum(_same_group(members, left, right) for left, right in case["forbidden_merge_pairs"])
    false_splits = sum(not _same_group(members, left, right) for left, right in case["required_group_pairs"])
    generic = {"failure", "error", "errors", "unknown", "generic"}
    candidate_total = len(case["expected_dispositions"].get("model_candidate", []))
    catchalls = sum(len(group.get("source_span", [])) / candidate_total > 0.8 and (str(group.get("pattern", "")).strip().lower() in generic or str(group.get("classification", "")).strip().lower() in generic) for group in groups) if candidate_total else 0
    needs_review = sum(bool(group.get("needs_review")) for group in groups)
    return {"false_merges": false_merges, "false_splits": false_splits, "catchalls": catchalls, "needs_review": needs_review, "operationally_useful": accepted and false_merges == 0 and false_splits == 0 and catchalls == 0}


def id_integrity(candidate: dict[str, Any] | None, expected_ids: set[str]) -> dict[str, int]:
    if not candidate:
        return {"invented_ids": 0, "duplicate_ids": 0, "omitted_candidate_ids": len(expected_ids)}
    claimed = [event_id for group in candidate.get("groups") or [] if isinstance(group, dict) for event_id in group.get("source_span") or []]
    claimed += list(candidate.get("ungrouped_candidate_ids") or [])
    counts = Counter(claimed)
    return {"invented_ids": len(set(claimed) - expected_ids), "duplicate_ids": sum(count - 1 for count in counts.values() if count > 1), "omitted_candidate_ids": len(expected_ids - set(claimed))}


def run_case(model: str, endpoint: str, case: dict[str, Any], listener: dict[str, Any]) -> dict[str, Any]:
    transport = ObservedTransport(model)
    output = log_process({"text": case["text"], "source": case["case_id"], "semantic": True}, active_policy(model, endpoint), transport=transport)
    candidates = output.get("data", {}).get("model_candidate_events", [])
    expected_ids = {event["event_id"] for event in candidates}
    validation = validate_v2_candidate(candidates, transport.candidate, catchall_share=0.8) if transport.candidate else {"accepted": False, "errors": ["candidate_not_returned"]}
    schema_valid = False
    if transport.candidate is not None:
        schema_valid = not list(Draft202012Validator(V2_CANDIDATE_RESPONSE_SCHEMA).iter_errors(transport.candidate))
    groups = output.get("data", {}).get("semantic_groups", [])
    accepted = bool(output.get("data", {}).get("semantic_accepted"))
    quality = semantic_quality(case, groups, accepted)
    integrity = id_integrity(transport.candidate, expected_ids)
    accounting = output.get("data", {}).get("accounting", {})
    rejection = [] if accepted else list(output.get("data", {}).get("fallback_reason", [])) or list(validation.get("errors", []))
    invalid_reason = None
    if transport.record["model_reported"] is not None and not transport.record["response_identity_match"]:
        invalid_reason = "response_model_identity_mismatch"
    elif not transport.record["exact_tag_present"]:
        invalid_reason = "required_mac_model_missing"
    return {
        "run_id": output.get("run_id"), "run_status": "invalid" if invalid_reason else "valid", "failure_reason": invalid_reason,
        "model_requested": model, "model_reported": transport.record["model_reported"], "endpoint": endpoint, "physical_execution_host": "Mac", "listener_verified": listener["verified"],
        "case_id": case["case_id"], "fixture_hash": case["fixture_hash"], "observed_event_count": case["observed_event_count"], "model_candidate_count": len(candidates),
        "preflight": {"tags_checked": transport.record["tags_checked"], "exact_tag_present": transport.record["exact_tag_present"]},
        "transport": {"attempted": transport.record["attempted"], "succeeded": transport.record["succeeded"], "latency_ms": transport.record["latency_ms"], "timeout": transport.record["timeout"]},
        "request_fingerprints": {"prompt_hash": transport.record["prompt_hash"], "schema_hash": transport.record["schema_hash"], "options_hash": transport.record["options_hash"]},
        "candidate": {"returned": transport.record["candidate_returned"], "schema_valid": schema_valid, "evidence_valid": validation["accepted"], "accepted": accepted, "rejection_reason": rejection},
        "accounting": {"fully_accounted": accounting.get("fully_accounted", False), **integrity, "fallback_coverage": 1.0 if output.get("data", {}).get("fallback_used") and accounting.get("fully_accounted") else (None if not output.get("data", {}).get("fallback_used") else 0.0)},
        "semantic": {"false_merges": quality["false_merges"], "false_splits": quality["false_splits"], "catch_all_groups": quality["catchalls"], "needs_review_groups": quality["needs_review"], "unclassified_observed": accounting.get("unclassified_observed_total", 0), "operationally_useful": quality["operationally_useful"]},
        "fallback": {"used": bool(output.get("data", {}).get("fallback_used")), "reason": list(output.get("data", {}).get("fallback_reason", []))},
        "safety": {"raw_response_stored": False, "external_internet_inference_observed": False, "endpoint_fallback_used": False},
    }


def aggregate(model: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [row["transport"]["latency_ms"] for row in rows if isinstance(row["transport"]["latency_ms"], int)]
    fallback_rows = [row for row in rows if row["fallback"]["used"]]
    return {
        "model": model, "cases_fully_accounted": sum(row["accounting"]["fully_accounted"] for row in rows),
        "invented_id_count": sum(row["accounting"]["invented_ids"] for row in rows),
        "duplicate_id_count": sum(row["accounting"]["duplicate_ids"] for row in rows),
        "omitted_candidate_id_count": sum(row["accounting"]["omitted_candidate_ids"] for row in rows),
        "invented_accepted_id_count": sum(row["accounting"]["invented_ids"] for row in rows if row["candidate"]["accepted"]),
        "duplicate_accepted_id_count": sum(row["accounting"]["duplicate_ids"] for row in rows if row["candidate"]["accepted"]),
        "omitted_accepted_candidate_id_count": sum(row["accounting"]["omitted_candidate_ids"] for row in rows if row["candidate"]["accepted"]),
        "fallback_coverage_rate": min((row["accounting"]["fallback_coverage"] for row in fallback_rows), default=1.0),
        "unclassified_observed_count": sum(row["semantic"]["unclassified_observed"] for row in rows),
        "candidate_returned_count": sum(row["candidate"]["returned"] for row in rows), "schema_valid_count": sum(row["candidate"]["schema_valid"] for row in rows), "evidence_valid_count": sum(row["candidate"]["evidence_valid"] for row in rows),
        "accepted_candidate_count": sum(row["candidate"]["accepted"] for row in rows), "rejected_candidate_count": sum(not row["candidate"]["accepted"] for row in rows), "fallback_count": len(fallback_rows),
        "false_merge_count": sum(row["semantic"]["false_merges"] for row in rows), "false_split_count": sum(row["semantic"]["false_splits"] for row in rows), "catch_all_group_count": sum(row["semantic"]["catch_all_groups"] for row in rows), "needs_review_count": sum(row["semantic"]["needs_review_groups"] for row in rows), "operationally_useful_cases": sum(row["semantic"]["operationally_useful"] for row in rows),
        "median_latency_ms": round(statistics.median(latencies)) if latencies else None, "max_latency_ms": max(latencies) if latencies else None, "timeout_count": sum(row["transport"]["timeout"] for row in rows), "transport_failure_count": sum(row["transport"]["attempted"] and not row["transport"]["succeeded"] for row in rows),
    }


def comparison(aggregates: list[dict[str, Any]]) -> dict[str, Any]:
    qualified = [row["model"] for row in aggregates if row["invented_accepted_id_count"] == row["duplicate_accepted_id_count"] == row["omitted_accepted_candidate_id_count"] == 0 and row["fallback_coverage_rate"] == 1.0]
    def leaders(key: str, *, lower: bool = False) -> list[str]:
        eligible = [row for row in aggregates if row["model"] in qualified and row[key] is not None]
        if not eligible: return []
        target = (min if lower else max)(row[key] for row in eligible)
        return [row["model"] for row in eligible if row[key] == target]
    return {"safety_qualified_models": qualified, "highest_acceptance": leaders("accepted_candidate_count"), "lowest_fallback": leaders("fallback_count", lower=True), "lowest_false_merge": leaders("false_merge_count", lower=True), "lowest_review_burden": leaders("needs_review_count", lower=True), "fastest": leaders("median_latency_ms", lower=True), "highest_operational_usefulness": leaders("operationally_useful_cases"), "winner": "NOT ESTABLISHED", "confidence": "insufficient_five_case_corpus"}


def write_output(path: Path, evidence: dict[str, Any]) -> None:
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_cli(args)
        listener = verify_listener()
        before = corpus_snapshot(args.corpus)
        corpus = load_corpus(args.corpus)
        initial_tags = exact_tags()
        missing = [model for model in args.models if model not in initial_tags]
        if missing:
            evidence = {"execution_status": "BLOCKED", "reason": "required_mac_model_missing", "missing_model": missing[0], "completed_runs_before_stop": 0, "listener": listener, "corpus_before": before, "raw_provider_response_stored": False}
            write_output(args.output, evidence)
            print(canonical_json({"execution_status": "BLOCKED", "reason": evidence["reason"], "missing_model": missing[0]}))
            return 2
        runs: list[dict[str, Any]] = []
        for model in args.models:
            for case in corpus["cases"]:
                run = run_case(model, args.endpoint, case, listener)
                runs.append(run)
                if run["run_status"] == "invalid":
                    evidence = {"execution_status": "BLOCKED", "reason": run["failure_reason"], "completed_runs_before_stop": len(runs), "listener": listener, "corpus_before": before, "runs": runs, "raw_provider_response_stored": False}
                    write_output(args.output, evidence)
                    print(canonical_json({"execution_status": "BLOCKED", "reason": evidence["reason"], "completed_runs_before_stop": len(runs)}))
                    return 2
        after = corpus_snapshot(args.corpus)
        if after != before:
            evidence = {"execution_status": "INVALID", "reason": "frozen_corpus_changed", "listener": listener, "corpus_before": before, "corpus_after": after, "runs": runs, "raw_provider_response_stored": False}
            write_output(args.output, evidence)
            print(canonical_json({"execution_status": "INVALID", "reason": evidence["reason"]}))
            return 2
        aggregates = [aggregate(model, [run for run in runs if run["model_requested"] == model]) for model in args.models]
        prompt_hashes = {case["case_id"]: sorted({run["request_fingerprints"]["prompt_hash"] for run in runs if run["case_id"] == case["case_id"]}) for case in corpus["cases"]}
        if any(len(values) != 1 for values in prompt_hashes.values()):
            raise ValueError("prompt_changed_between_models")
        evidence = {
            "evidence_version": "2.0.0", "execution_status": "COMPLETE", "contract_version": args.contract_version, "endpoint": args.endpoint, "models": args.models,
            "listener": listener, "corpus_before": before, "corpus_after": after, "corpus_unchanged": True,
            "configuration_fingerprints": {"prompt_hashes_by_case": {key: values[0] for key, values in prompt_hashes.items()}, "schema_hash": _hash(V2_CANDIDATE_RESPONSE_SCHEMA), "validator_hash": sha256(inspect.getsource(validate_v2_candidate).encode()).hexdigest(), "options_hash": _hash({"stream": False, "think": False, "options": {"temperature": 0}})},
            "expected_runs": len(args.models) * len(corpus["cases"]), "attempted_runs": len(runs), "valid_runs": sum(run["run_status"] == "valid" for run in runs), "invalid_runs": sum(run["run_status"] != "valid" for run in runs), "infrastructure_retries": 0,
            "runs": runs, "per_model": aggregates, "comparison": comparison(aggregates),
            "safety": {"physical_execution_host": "Mac", "external_internet_inference_observed": False, "raw_provider_response_stored": False, "endpoint_fallback_used": False, "model_pull_performed": False},
        }
        write_output(args.output, evidence)
        print(canonical_json({key: evidence[key] for key in ("execution_status", "endpoint", "models", "expected_runs", "attempted_runs", "valid_runs", "invalid_runs", "comparison", "safety")}))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(canonical_json({"execution_status": "BLOCKED", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
