import json
from pathlib import Path

from local_developer_worker.tools import parse_log


def test_generic_log_golden_fixture():
    root = Path(__file__).parents[2]
    fixture = (root / "fixtures" / "synthetic" / "generic.log").read_text()
    expected = json.loads((root / "fixtures" / "expected" / "generic_log.json").read_text())
    events = parse_log({"text": fixture})["data"]["events"]
    assert [[event["level"], event["parse_status"]] for event in events] == expected["states"]
