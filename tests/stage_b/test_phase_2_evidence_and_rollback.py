from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_pb2_07_supervised_evidence_records_a_real_response_without_raw_content():
    evidence = json.loads((ROOT / "fixtures" / "stage_b" / "phase_2_live_run_evidence.json").read_text())

    assert evidence["classification"] == "OBSERVED"
    assert evidence["command"] == "ldw log cluster"
    assert evidence["corpus"] == "REF-01"
    assert evidence["model"] == "qwen3:4b"
    assert evidence["endpoint"] == "http://127.0.0.1:11435/api/generate"
    assert evidence["model_response_observed"] is True
    assert evidence["tool_status"] == "partial"
    assert evidence["fallback_used"] is True
    assert evidence["fallback_reason"] == [
        "duplicate_event_accounting",
        "invented_source",
        "source_span_recall_failed",
    ]
    assert evidence["observed_event_count"] == 34
    assert evidence["raw_response_stored"] is False
    assert evidence["code_artifact"] == "disabled"
    assert evidence["mutation_capabilities_granted"] is False
    assert "response" not in evidence


def test_pb2_08_rollback_disables_dispatch_and_preserves_past_candidate_evidence():
    text = (ROOT / "docs" / "stage-b-phase-2-rollback.md").read_text()

    assert "[semantic].enabled = false" in text
    assert "[automatic].semantic_log_clustering = false" in text
    assert 'code_artifact = "disabled"' in text
    assert "returns `policy_blocked`" in text
    assert "does not relabel, delete, or mutate historical packages" in text
    assert "model-derived" in text
