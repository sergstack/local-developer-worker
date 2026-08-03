from local_developer_worker.contracts import valid_tool_result
from local_developer_worker.tools import parse_log


def test_valid_tool_result_rejects_unknown_version_and_missing_manifest():
    output = parse_log({"text": "INFO ok"})
    assert valid_tool_result(output)
    output["schema_version"] = "2.0.0"
    assert not valid_tool_result(output)
    output["schema_version"] = "1.0.0"
    del output["input_manifest"]
    assert not valid_tool_result(output)
