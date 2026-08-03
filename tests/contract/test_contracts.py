import json
from pathlib import Path

from jsonschema import validate
from local_developer_worker.tools import parse_log


def test_tool_result_matches_schema():
    schema = json.loads((Path(__file__).parents[2] / "schemas" / "tool_result.schema.json").read_text())
    validate(parse_log({"text": "INFO hello"}), schema)
