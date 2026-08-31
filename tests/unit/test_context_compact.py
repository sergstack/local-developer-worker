from local_developer_worker.tools import COMPACTION_PRESERVATION_FIELDS, context_compact


def _preservation():
    return {field: [] for field in COMPACTION_PRESERVATION_FIELDS}


def test_context_compact_preserves_every_declared_critical_field_exactly():
    state = _preservation()
    state["goal"] = "Fix parser"
    state["authority_state"] = {"status": "owner_review_pending"}
    output = context_compact({"preservation": state, "candidate_summary": "Candidate-only summary", "dropped_items": [{"id": "chat-1", "reason": "repetitive"}], "original_context_bytes": 2000})
    assert output["status"] == "success"
    assert output["data"]["preserved_items"] == state
    assert output["data"]["candidate_summary_authoritative"] is False
    assert output["data"]["local_model_usage"] == {"used": False}
    assert output["data"]["metrics"]["context_bytes_reduced"] > 0


def test_context_compact_fails_visibly_when_critical_state_or_measurement_is_missing():
    state = _preservation()
    state.pop("evidence_refs")
    incomplete = context_compact({"preservation": state, "original_context_bytes": 1000})
    assert incomplete["status"] == "partial"
    assert incomplete["errors"][0]["code"] == "preservation_incomplete"
    invalid = context_compact({"preservation": _preservation(), "original_context_bytes": 0})
    assert invalid["status"] == "partial"
    assert invalid["errors"][0]["code"] == "invalid_compaction_measurement"
