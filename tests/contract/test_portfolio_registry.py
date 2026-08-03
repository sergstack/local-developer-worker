import json
import copy
from pathlib import Path

from jsonschema import validate

from local_developer_worker.portfolio import load_registry, render_release_gates

ROOT = Path(__file__).parents[2]


def test_portfolio_registry_has_exactly_twenty_schema_valid_items():
    registry = load_registry()
    schema = json.loads((ROOT / "schemas" / "portfolio_item.schema.json").read_text())
    for item in registry["items"]:
        validate(instance=item, schema=schema)

    assert [item["id"] for item in registry["items"]] == [f"SA-{index:02d}" for index in range(1, 17)] + [f"AI-{index:02d}" for index in range(1, 5)]
    assert [item["category"] for item in registry["items"]].count("gate") == 16
    assert [item["category"] for item in registry["items"]].count("action_item") == 4


def test_release_gate_document_is_byte_identical_to_registry_rendering():
    expected = render_release_gates(load_registry()).encode()
    assert (ROOT / "docs" / "release-gates.md").read_bytes() == expected


def test_ai02_records_advisory_choice_and_rejects_session_wrapper():
    ai02 = next(item for item in load_registry()["items"] if item["id"] == "AI-02")
    assert ai02["decision"]["chosen_option"] == "a"
    assert ai02["forced_status"] == "waiting_for_input"
    assert [option["id"] for option in ai02["decision_options"]] == ["a", "b", "c"]
    assert next(option for option in ai02["decision_options"] if option["id"] == "b")["rejected"] is True
    assert [check["check_id"] for check in ai02["artifacts"]] == ["AI-02-agents-rule", "AI-02-doctor-reminder"]


def test_runtime_registry_loader_rejects_session_wrapper_decision(tmp_path):
    malformed = copy.deepcopy(load_registry())
    malformed["items"][17]["decision"]["chosen_option"] = "b"
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(malformed))

    try:
        load_registry(path)
    except ValueError as exc:
        assert "allowed option" in str(exc)
    else:
        raise AssertionError("rejected session wrapper decision was accepted")


def test_runtime_registry_loader_rejects_malformed_items(tmp_path):
    malformed = copy.deepcopy(load_registry())
    malformed["items"][0]["evidence_test_ids"] = ["not-an-exact-pytest-node"]
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(malformed))

    try:
        load_registry(path)
    except ValueError as exc:
        assert "evidence tests" in str(exc)
    else:
        raise AssertionError("malformed registry was accepted")


def test_runtime_registry_loader_rejects_path_escape(tmp_path):
    malformed = copy.deepcopy(load_registry())
    malformed["items"][16]["artifacts"][0]["path"] = "../../outside"
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(malformed))

    try:
        load_registry(path)
    except ValueError as exc:
        assert "unsafe artifact path" in str(exc)
    else:
        raise AssertionError("unsafe artifact path was accepted")
