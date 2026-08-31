import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from local_developer_worker.review import build_review_package, build_review_package_v1_1, review_build


def payload():
    return {
        "contract_version": "1.0.0",
        "objective": "Add a bounded deterministic review contract.",
        "scope": {
            "scope_id": "SCOPE_001",
            "change_size": "local",
            "changed_components": [{"component_id": "COMPONENT_CLI", "kind": "source"}],
            "declared_boundaries": ["cli"],
            "contract_change": False,
        },
        "git_facts": {
            "source_tool": "git_facts_collector",
            "source_run_id": "RUN_GIT_001",
            "working_tree_clean": False,
            "changed_component_ids": ["COMPONENT_CLI"],
        },
        "evidence": {
            "source_tool": "evidence_package_builder",
            "source_run_id": "RUN_EVIDENCE_001",
            "content_hash": "a" * 64,
            "lineage_complete": True,
            "observed_evidence_refs": ["EV_TEST_001", "EV_GIT_001"],
            "candidate_evidence_refs": ["CANDIDATE_001"],
            "missing_evidence_ids": [],
            "unknown_ids": [],
        },
        "required_checks": [
            {
                "check_id": "CHECK_GIT_001",
                "check_type": "git",
                "status": "passed",
                "source_tool": "git_facts_collector",
                "evidence_refs": ["EV_GIT_001"],
            },
            {
                "check_id": "CHECK_TEST_001",
                "check_type": "test",
                "status": "passed",
                "source_tool": "test_result_parser",
                "evidence_refs": ["EV_TEST_001"],
            },
        ],
    }


def schema(name):
    path = Path(__file__).parents[2] / "schemas" / name
    return Draft202012Validator(json.loads(path.read_text()))


def test_review_package_is_deterministic_and_non_authoritative():
    review_input = payload()
    first = build_review_package(review_input)
    second = build_review_package(copy.deepcopy(review_input))

    assert first == second
    assert first["review_profile"] == "local"
    assert first["derived_view_plan"]["rendering"] == "not_in_p0"
    assert first["authority"] == {
        "evidence_manifest_authoritative": True,
        "review_package_status": "derived",
        "promotion_authority": "human_or_ai_os_only",
        "model_invoked": False,
        "source_mutation": False,
        "root_cause_inferred": False,
    }
    schema("review_build_input_v1.schema.json").validate(review_input)
    schema("review_package_v1.schema.json").validate(first)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda value: value["scope"].update({"contract_change": True}), "contract_change"),
        (lambda value: value["scope"].update({"change_size": "cross_boundary"}), "cross_boundary"),
        (lambda value: value["scope"].update({"declared_boundaries": ["cli", "contracts"]}), "cross_boundary"),
        (lambda value: value["evidence"].update({"unknown_ids": ["UNKNOWN_001"]}), "evidence_risk"),
        (lambda value: value["required_checks"][0].update({"status": "not_run", "source_tool": "none", "evidence_refs": []}), "evidence_risk"),
    ],
)
def test_router_profiles_are_deterministic(mutate, expected):
    review_input = payload()
    mutate(review_input)
    assert build_review_package(review_input)["review_profile"] == expected


def test_unknown_and_not_run_stay_visible_not_observed():
    review_input = payload()
    review_input["evidence"]["missing_evidence_ids"] = ["MISSING_CHECK_001"]
    review_input["required_checks"][1].update({"status": "not_run", "source_tool": "none", "evidence_refs": []})

    package = build_review_package(review_input)

    assert package["review_profile"] == "evidence_risk"
    assert package["unknowns"] == ["CHECK_TEST_001", "MISSING_CHECK_001"]
    assert package["findings"][1]["evidence_state"] == "not_run"
    assert package["findings"][1]["evidence_refs"] == []


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda value: value.update({"raw_evidence": "forbidden"}), "invalid_review_build_input"),
        (lambda value: value["evidence"].update({"raw_content": "forbidden"}), "invalid_review_evidence"),
        (lambda value: value["required_checks"][1].update({"source_tool": "none"}), "test_check_requires_test_parser"),
        (lambda value: value["required_checks"][1].update({"evidence_refs": ["EV_UNKNOWN"]}), "observed_check_requires_observed_evidence"),
        (lambda value: value["evidence"].update({"candidate_evidence_refs": ["EV_TEST_001"]}), "evidence_reference_state_conflict"),
        (lambda value: value["git_facts"].update({"changed_component_ids": ["COMPONENT_OTHER"]}), "git_component_outside_scope"),
    ],
)
def test_rejects_raw_unobserved_or_out_of_scope_inputs(mutate, error):
    review_input = payload()
    mutate(review_input)

    with pytest.raises(ValueError, match=error):
        build_review_package(review_input)


def test_tool_result_exposes_invalid_input_without_partial_package():
    review_input = payload()
    review_input["required_checks"][0]["status"] = "unknown"

    outcome = review_build(review_input)

    assert outcome["status"] == "invalid_input"
    assert outcome["data"] == {}
    assert outcome["errors"][0]["code"] == "unobserved_check_must_not_claim_evidence"


def p1_payload():
    value = payload()
    value["contract_version"] = "1.1.0"
    value["scope"]["contract_change"] = True
    value["contract_comparison"] = {
        "availability": "available",
        "unavailable_reason_id": None,
        "baseline": {"contract_id": "CONTRACT_BASELINE", "version_label": "1.0.0", "content_hash": "b" * 64},
        "candidate": {"contract_id": "CONTRACT_CANDIDATE", "version_label": "1.1.0", "content_hash": "c" * 64},
        "added_field_ids": ["FIELD_LEDGER"],
        "removed_field_ids": [],
        "changed_field_ids": ["FIELD_EXPORT"],
    }
    return value


def test_p1_builds_derived_evidence_ledger_and_structural_delta():
    review_input = p1_payload()
    package = build_review_package_v1_1(review_input)

    assert package["contract_version"] == "1.1.0"
    assert package["review_profile"] == "contract_change"
    assert package["evidence_ledger"]["derived"] is True
    assert package["evidence_ledger"]["authoritative_input"] == "caller_retained_evidence"
    assert {row["state"] for row in package["evidence_ledger"]["rows"]} == {"observed", "candidate"}
    assert package["contract_delta"] == {
        "status": "structural_delta",
        "baseline": review_input["contract_comparison"]["baseline"],
        "candidate": review_input["contract_comparison"]["candidate"],
        "added_field_ids": ["FIELD_LEDGER"],
        "removed_field_ids": [],
        "changed_field_ids": ["FIELD_EXPORT"],
        "compatibility_assessment": "not_in_p1",
    }
    schema("review_build_input_v1_1.schema.json").validate(review_input)
    schema("review_package_v1_1.schema.json").validate(package)


def test_p1_preserves_unavailable_comparison_and_unknown_evidence():
    review_input = p1_payload()
    review_input["contract_comparison"] = {
        "availability": "unavailable", "unavailable_reason_id": "COMPARISON_INPUT_MISSING",
        "baseline": None, "candidate": None, "added_field_ids": None, "removed_field_ids": None, "changed_field_ids": None,
    }
    review_input["evidence"]["unknown_ids"] = ["UNKNOWN_EVIDENCE"]
    review_input["required_checks"][1].update({"status": "unknown", "source_tool": "none", "evidence_refs": []})

    package = build_review_package_v1_1(review_input)

    assert package["review_profile"] == "evidence_risk"
    assert package["contract_delta"] == {"status": "unavailable", "unavailable_reason_id": "COMPARISON_INPUT_MISSING"}
    assert {row["state"] for row in package["evidence_ledger"]["rows"]} >= {"observed", "candidate", "unknown"}
    assert any(row.get("check_id") == "CHECK_TEST_001" and row["state"] == "unknown" for row in package["evidence_ledger"]["rows"])


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda value: value["contract_comparison"].update({"raw_contract": "forbidden"}), "invalid_contract_comparison"),
        (lambda value: value["contract_comparison"].update({"added_field_ids": [], "removed_field_ids": [], "changed_field_ids": []}), "contract_comparison_requires_declared_delta"),
        (lambda value: value["contract_comparison"].update({"candidate": {"contract_id": "CONTRACT_CANDIDATE", "version_label": "1.1.0", "content_hash": "b" * 64}}), "contract_comparison_requires_distinct_hashes"),
        (lambda value: value["contract_comparison"].update({"removed_field_ids": ["FIELD_LEDGER"]}), "contract_delta_field_state_conflict"),
    ],
)
def test_p1_rejects_raw_or_ambiguous_contract_comparisons(mutate, error):
    review_input = p1_payload()
    mutate(review_input)

    with pytest.raises(ValueError, match=error):
        build_review_package_v1_1(review_input)
