import json
from pathlib import Path

from jsonschema import validate

from local_developer_worker.stage_b_phase_2_portfolio import EXPECTED_IDS, load_phase_2_registry


ROOT = Path(__file__).parents[2]


def test_phase_2_registry_has_exactly_eight_schema_valid_objects():
    registry = load_phase_2_registry()
    schema = json.loads((ROOT / "schemas" / "stage_b_phase_2_portfolio_item.schema.json").read_text())

    assert [item["id"] for item in registry["items"]] == EXPECTED_IDS
    for item in registry["items"]:
        validate(item, schema)
