from __future__ import annotations

from local_developer_worker.log_process import log_process
from local_developer_worker.policy import root_allowed


def _policy(**semantic):
    return {"automatic": {"semantic_log_clustering": True}, "semantic": {"enabled": True, "code_artifact": "disabled", "model": "qwen3:8b", "endpoint": "http://127.0.0.1:11435/api/generate", "routing_event_threshold": 2, **semantic}, "limits": {"timeout_seconds": 60}}


def _candidate(ids, ungrouped=()):
    grouped = [event_id for event_id in ids if event_id not in ungrouped]
    groups = [] if not grouped else [{"group_id": "SG-ONE", "pattern": "database connection failure", "classification": "database_connection", "source_span": grouped, "confidence": 0.9, "origin": "model-derived", "needs_review": False}]
    return {"contract_version": 2, "groups": groups, "ungrouped_candidate_ids": list(ungrouped)}


def test_unknown_and_continuation_have_explicit_dispositions():
    output = log_process({"text": "ERROR failure\n  trace detail\nopaque record", "semantic": False}, _policy())
    rows = output["data"]["initial_dispositions"]
    assert rows[1]["disposition"] == "structural_continuation"
    assert rows[1]["parent_event_id"] == "EV-000001"
    assert rows[2]["disposition"] == "model_candidate"
    assert output["data"]["accounting"]["fully_accounted"] is True


def test_candidate_payload_is_bounded_and_valid_v2_is_accepted():
    calls = []
    def transport(_endpoint, request):
        calls.append(request)
        return _candidate(["EV-000001", "EV-000002"])
    output = log_process({"text": "ERROR database unavailable\nERROR database unavailable", "semantic": True}, _policy(), transport=transport)
    assert output["data"]["semantic_accepted"] is True
    assert output["data"]["accounting"]["semantically_grouped_total"] == 2
    assert "candidate_events" in calls[0]["prompt"]
    assert "excluded" not in calls[0]["prompt"]


def test_invented_duplicate_or_omitted_ids_fall_back_with_full_coverage():
    bad = [
        _candidate(["EV-000001", "EV-999999"]),
        {"contract_version": 2, "groups": [{"group_id": "SG-ONE", "pattern": "x", "classification": "x", "source_span": ["EV-000001", "EV-000001"], "confidence": .9, "origin": "model-derived", "needs_review": False}], "ungrouped_candidate_ids": ["EV-000002"]},
        _candidate(["EV-000001"]),
    ]
    for response in bad:
        output = log_process({"text": "ERROR one\nERROR two", "semantic": True}, _policy(), transport=lambda *_: response)
        assert output["data"]["fallback_used"] is True
        assert output["data"]["accounting"]["fallback_observed_total"] == 2


def test_ungrouped_no_raw_response_and_nonloopback_blocked():
    response = _candidate(["EV-000001", "EV-000002"], ["EV-000002"])
    output = log_process({"text": "ERROR one\nERROR two", "semantic": True}, _policy(), transport=lambda *_: {**response, "raw_provider_response": "do-not-persist"})
    assert output["data"]["accounting"]["semantic_ungrouped_total"] == 1
    assert "do-not-persist" not in str(output)
    calls = []
    blocked = log_process({"text": "ERROR one\nERROR two", "semantic": True}, _policy(endpoint="http://203.0.113.1"), transport=lambda *a: calls.append(a))
    assert blocked["status"] == "policy_blocked" and calls == []


def test_balanced_profile_keeps_repository_tools_root_gated(tmp_path):
    import tomllib
    from pathlib import Path
    with (Path(__file__).parents[2] / "examples" / "policies" / "balanced.toml").open("rb") as handle:
        policy = tomllib.load(handle)
    assert policy["automatic"]["semantic_log_clustering"] is True
    assert policy["semantic"]["enabled"] is True
    assert policy["semantic"]["code_artifact"] == "disabled"
    assert root_allowed(policy, str(tmp_path), Path.cwd()) is False


def test_known_info_metadata_is_deterministically_excluded():
    output = log_process({"text": "INFO service started", "semantic": False}, _policy())
    row = output["data"]["initial_dispositions"][0]
    assert row["disposition"] == "deterministically_excluded"
    assert row["reason_code"] == "known_non_failure_metadata"


def test_timeout_before_execution_uses_full_observed_fallback():
    calls = []
    policy = _policy()
    policy["limits"]["timeout_seconds"] = 0
    output = log_process(
        {"text": "ERROR database unavailable\nERROR database unavailable", "semantic": True},
        policy,
        transport=lambda *args: calls.append(args),
    )
    assert calls == []
    assert output["data"]["semantic_attempted"] is False
    assert output["data"]["fallback_used"] is True
    assert output["data"]["fallback_reason"] == ["timeout_before_execution"]
    assert output["data"]["accounting"]["fallback_observed_total"] == 2
    assert output["data"]["accounting"]["fully_accounted"] is True


def test_automatic_routing_requires_explicit_policy_opt_in():
    response = _candidate(["EV-000001", "EV-000002"])
    calls = []
    explicit_only = log_process(
        {"text": "ERROR database unavailable\nERROR database unavailable"},
        _policy(),
        transport=lambda *args: calls.append(args),
    )
    assert explicit_only["data"]["semantic_attempted"] is False
    assert calls == []

    automatic = log_process(
        {"text": "ERROR database unavailable\nERROR database unavailable"},
        _policy(automatic_routing=True),
        transport=lambda *_: response,
    )
    assert automatic["data"]["semantic_attempted"] is True
    assert automatic["data"]["semantic_accepted"] is True
