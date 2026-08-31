import pytest
from local_developer_worker.rework_miner import analyze

def payload():
    return {"contract_version":"1.0.0","cohort_id":"COHORT_001","observations":[
        {"session_id":"SESSION_001","root_class":"execution","signal":"turn_aborted","occurrence_count":2,"evidence_refs":["EV_001"]},
        {"session_id":"SESSION_002","root_class":"execution","signal":"turn_aborted","occurrence_count":3,"evidence_refs":["EV_002"]}]}

def test_candidate_only_pareto_summary():
    data=analyze(payload())
    assert data["candidates"][0]["occurrence_count"] == 5
    assert data["candidates"][0]["promotion_status"] == "candidate_only"
    assert data["privacy"]["model_invoked"] is False

def test_rejects_raw_and_duplicate_inputs():
    raw=payload(); raw["observations"][0]["prompt"]="forbidden"
    with pytest.raises(ValueError): analyze(raw)
    raw=payload(); raw["observations"][1]["session_id"]="SESSION_001"
    with pytest.raises(ValueError, match="duplicate_session_id"): analyze(raw)
