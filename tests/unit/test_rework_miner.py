import pytest
from local_developer_worker.rework_miner import analyze, prepare_sanitized_excerpts, validate_candidate_lesson

def payload():
    return {"contract_version":"1.0.0","cohort_id":"COHORT_001","observations":[
        {"observation_id":"OBS_001","session_id":"SESSION_001","root_class":"execution","signal":"turn_aborted","occurrence_count":2,"evidence_refs":["EV_001"]},
        {"observation_id":"OBS_002","session_id":"SESSION_002","root_class":"execution","signal":"turn_aborted","occurrence_count":3,"evidence_refs":["EV_002"]}]}

def test_candidate_only_pareto_summary():
    data=analyze(payload())
    assert data["candidates"][0]["occurrence_count"] == 5
    assert data["candidates"][0]["promotion_status"] == "candidate_only"
    assert data["privacy"]["model_invoked"] is False


def test_structural_excerpt_package_excludes_session_identifiers():
    data = prepare_sanitized_excerpts(payload())
    assert data["excerpt_count"] == 1
    assert data["excerpts"][0]["human_correction_status"] == "not_observed"
    assert "session_id" not in data["excerpts"][0]
    assert data["privacy"]["session_ids_exported"] is False

def test_rejects_raw_and_duplicate_inputs():
    raw=payload(); raw["observations"][0]["prompt"]="forbidden"
    with pytest.raises(ValueError): analyze(raw)
    raw=payload(); raw["observations"][1]["observation_id"]="OBS_001"
    with pytest.raises(ValueError, match="duplicate_observation_id"): analyze(raw)


def candidate_payload():
    return {"contract_version": "1.0.0", "allowed_evidence_refs": ["EV_001", "EV_002"], "candidate": {
        "candidate_id": "CANDIDATE_001", "trigger": "repeated_tool_call", "observed_problem": "Repeated execution signal.",
        "human_correction": "Use the existing deterministic path first.", "rework_class": "execution",
        "generalizable_rule": "Prefer the known deterministic path before retrying.", "scope": "LDW execution handling",
        "counterexamples": ["Do not apply when the path is unavailable."], "evidence_refs": ["EV_001"],
        "occurrence_count": 3, "candidate_destination": "execution_handling", "confidence": "low",
    }}


def test_candidate_lesson_is_validated_but_never_promoted():
    data = validate_candidate_lesson(candidate_payload())
    assert data["validation"]["schema"] == "passed"
    assert data["validation"]["promotion_status"] == "candidate_only"
    assert data["validation"]["reuse_status"] == "judge_required"
    assert data["privacy"]["model_invoked"] is False


@pytest.mark.parametrize("field,value,error", [
    ("evidence_refs", ["EV_UNKNOWN"], "unknown_evidence_ref"),
    ("human_correction", "raw\x01control", "invalid_human_correction"),
    ("candidate_destination", "auto_promote", "invalid_candidate_disposition"),
])
def test_candidate_lesson_rejects_untrusted_or_invalid_content(field, value, error):
    raw = candidate_payload(); raw["candidate"][field] = value
    with pytest.raises(ValueError, match=error):
        validate_candidate_lesson(raw)
