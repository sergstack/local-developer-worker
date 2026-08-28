from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from local_developer_worker.ollama_advisory_study import analyze_manifest, validate_manifest


FIXTURE = Path(__file__).parents[2] / "fixtures" / "ollama_advisory_study" / "dry_run_manifest.json"


def _manifest() -> dict:
    return json.loads(FIXTURE.read_text())


def test_dry_run_is_informational_even_when_all_metrics_are_better():
    result = analyze_manifest(_manifest())
    assert result["task_classes"][0]["decision"] == "INSUFFICIENT_EVIDENCE"
    assert result["task_classes"][1]["decision"] == "INSUFFICIENT_EVIDENCE"
    assert result["privacy"]["prompts_or_model_responses_persisted"] is False


def test_live_codex_review_required_task_is_denied_even_with_good_aggregates():
    manifest = _manifest()
    manifest["mode"] = "live"
    manifest["evidence_status"] = "observed"
    result = analyze_manifest(manifest)
    review = next(row for row in result["task_classes"] if row["task_class"] == "one_off_code_review")
    assert review["decision"] == "DENY"
    assert review["reason"] == "codex_review_required_adds_an_unmeasured_or_extra_review_loop"


def test_live_terminal_task_requires_all_three_metrics_and_acceptance():
    manifest = _manifest()
    manifest["mode"] = "live"
    manifest["evidence_status"] = "observed"
    original = copy.deepcopy(manifest["pairs"][0])
    for number in range(2, 6):
        pair = copy.deepcopy(original)
        pair["pair_id"] = f"TRIAGE-{number:03d}"
        manifest["pairs"].append(pair)
    result = analyze_manifest(manifest)
    triage = next(row for row in result["task_classes"] if row["task_class"] == "bounded_batch_triage")
    assert triage["decision"] == "PERMIT"
    failed = copy.deepcopy(manifest)
    for pair in failed["pairs"]:
        if pair["task_class"] == "bounded_batch_triage":
            pair["candidate"]["development_latency_ms"] = 1000
    result = analyze_manifest(failed)
    triage = next(row for row in result["task_classes"] if row["task_class"] == "bounded_batch_triage")
    assert triage["decision"] == "DENY"


def test_live_single_pair_cannot_authorize_a_task_class():
    manifest = _manifest()
    manifest["mode"] = "live"
    manifest["evidence_status"] = "observed"
    manifest["pairs"] = [manifest["pairs"][0]]
    result = analyze_manifest(manifest)
    assert result["task_classes"][0]["decision"] == "INSUFFICIENT_EVIDENCE"


def test_manifest_rejects_raw_task_or_output_fields():
    manifest = _manifest()
    manifest["pairs"][0]["prompt"] = "must never persist"
    with pytest.raises(ValueError, match="invalid_advisory_study_pair"):
        validate_manifest(manifest)


def test_unobserved_ollama_diagnostics_are_not_converted_to_zero():
    manifest = _manifest()
    candidate = manifest["pairs"][0]["candidate"]
    candidate["ollama_input_tokens"] = None
    candidate["ollama_output_tokens"] = None
    candidate["ollama_latency_ms"] = None
    validate_manifest(manifest)


def test_live_synthetic_measurements_cannot_authorize_a_task_class():
    manifest = _manifest()
    manifest["mode"] = "live"
    original = copy.deepcopy(manifest["pairs"][0])
    for number in range(2, 6):
        pair = copy.deepcopy(original)
        pair["pair_id"] = f"SYN-{number:03d}"
        manifest["pairs"].append(pair)
    result = analyze_manifest(manifest)
    assert result["task_classes"][0]["decision"] == "INSUFFICIENT_EVIDENCE"


def test_dry_run_script_is_reproducible_and_non_promoting():
    root = Path(__file__).parents[2]
    command = [sys.executable, "scripts/run_ollama_advisory_study.py", "fixtures/ollama_advisory_study/dry_run_manifest.json"]
    first = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True).stdout
    second = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True).stdout
    assert first == second
    assert {row["decision"] for row in json.loads(first)["task_classes"]} == {"INSUFFICIENT_EVIDENCE"}
