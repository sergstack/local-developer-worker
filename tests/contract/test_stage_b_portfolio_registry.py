import json
from pathlib import Path

from jsonschema import validate

from local_developer_worker.stage_b_portfolio import EXPECTED_IDS, load_phase_1_registry

ROOT = Path(__file__).parents[2]


def test_phase_1_registry_has_exactly_ten_schema_valid_objects():
    registry = load_phase_1_registry()
    schema = json.loads((ROOT / "schemas" / "stage_b_portfolio_item.schema.json").read_text())

    assert [item["id"] for item in registry["items"]] == EXPECTED_IDS
    assert len(registry["items"]) == 10
    for item in registry["items"]:
        validate(item, schema)


def test_policy_01_is_ready_and_not_waiting_for_owner():
    policy = load_phase_1_registry()["items"][0]

    assert policy["id"] == "POLICY-01"
    assert policy["initial_status"] == "ready"
