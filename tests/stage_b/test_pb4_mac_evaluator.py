from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
SPEC = importlib.util.spec_from_file_location("pb4_mac_evaluator", ROOT / "scripts" / "run_pb4_03_evaluation.py")
assert SPEC and SPEC.loader
evaluator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluator)


def _args(*extra):
    return evaluator.build_parser().parse_args([
        "--contract-version", "2", "--endpoint", evaluator.MAC_ENDPOINT,
        "--model", "qwen3:4b", "--corpus", str(ROOT / "fixtures" / "stage_b" / "pb4_v2_cases.json"),
        "--output", "/tmp/pb4-mac-evidence.json", *extra,
    ])


def test_evaluator_requires_explicit_endpoint_model_corpus_and_contract():
    parser = evaluator.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
    args = _args()
    evaluator.validate_cli(args)
    assert args.endpoint == "http://127.0.0.1:11435/api/generate"
    assert args.models == ["qwen3:4b"]


def test_evaluator_rejects_11434_and_unknown_or_duplicate_model_tags():
    args = _args()
    args.endpoint = "http://127.0.0.1:11434/api/generate"
    with pytest.raises(ValueError, match="mac_endpoint"):
        evaluator.validate_cli(args)
    args = _args()
    args.models = ["qwen3:4b", "qwen3:4b"]
    with pytest.raises(ValueError, match="duplicate"):
        evaluator.validate_cli(args)
    args.models = ["qwen3:4b-latest"]
    with pytest.raises(ValueError, match="unexpected_model_tag"):
        evaluator.validate_cli(args)


def test_frozen_corpus_snapshot_is_complete_and_stable():
    path = ROOT / "fixtures" / "stage_b" / "pb4_v2_cases.json"
    first = evaluator.corpus_snapshot(path)
    second = evaluator.corpus_snapshot(path)
    assert first == second
    assert first["case_count"] == 5
    assert len(first["cases"]) == 5
    assert first["manifest_hash"] == "51a983b4ed07c70bcfff7a3caadfc711c397ee7b55b8767300f63d0532522f0b"


def test_comparison_applies_safety_gate_and_does_not_claim_winner():
    rows = []
    for model, accepted, latency in (("qwen3:4b", 4, 20), ("qwen3:8b", 5, 30)):
        rows.append({"model": model, "invented_id_count": 1, "duplicate_id_count": 1, "omitted_candidate_id_count": 1, "invented_accepted_id_count": 0, "duplicate_accepted_id_count": 0, "omitted_accepted_candidate_id_count": 0, "fallback_coverage_rate": 1.0, "accepted_candidate_count": accepted, "fallback_count": 5 - accepted, "false_merge_count": 0, "needs_review_count": 0, "median_latency_ms": latency, "operationally_useful_cases": accepted})
    result = evaluator.comparison(rows)
    assert result["safety_qualified_models"] == ["qwen3:4b", "qwen3:8b"]
    assert result["highest_acceptance"] == ["qwen3:8b"]
    assert result["winner"] == "NOT ESTABLISHED"
