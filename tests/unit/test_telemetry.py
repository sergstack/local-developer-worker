import ast
from pathlib import Path

from local_developer_worker.telemetry import (
    KNOWN_ERROR_CODES,
    SAFE_FIELDS,
    USEFULNESS_MARK_FIELDS,
    telemetry_error_code,
    telemetry_event,
    usefulness_mark,
    valid_telemetry_event,
    valid_usefulness_mark,
)


def test_telemetry_drops_raw_content():
    event = telemetry_event({"tool": "log", "latency_ms": 3, "raw_log": "TOKEN=synthetic"})
    assert event["tool"] == "log"
    assert "raw_log" not in event
    assert set(event) == SAFE_FIELDS
    assert event["context_reduction"] is None
    assert event["error_code"] is None


def test_telemetry_error_code_prefers_first_error_then_first_warning():
    output = {
        "errors": [{"code": "invalid_json", "detail": "must-not-survive"}],
        "warnings": [{"code": "unknown_lines", "text": "must-not-survive"}],
    }

    assert telemetry_error_code(output) == "invalid_json"
    assert telemetry_error_code({"errors": [], "warnings": output["warnings"]}) == "unknown_lines"
    assert telemetry_error_code({"errors": [{"code": ["invalid_json"]}]}) is None


def test_telemetry_error_code_is_known_or_null_never_empty():
    assert telemetry_event({"error_code": "invalid_json"})["error_code"] == "invalid_json"
    assert telemetry_event({"error_code": ""})["error_code"] is None
    assert telemetry_event({"error_code": "provider-secret-detail"})["error_code"] is None
    assert telemetry_event({"error_code": ["invalid_json"]})["error_code"] is None
    assert not valid_telemetry_event({**telemetry_event({}), "error_code": "unknown_code"})
    assert not valid_telemetry_event({**telemetry_event({}), "error_code": ["invalid_json"]})


def test_known_error_codes_cover_all_literal_source_codes():
    source_root = Path(__file__).parents[2] / "src" / "local_developer_worker"
    literal_codes = set()
    for source_path in source_root.glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "code"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    literal_codes.add(value.value)

    assert literal_codes <= KNOWN_ERROR_CODES


def test_usefulness_mark_has_exact_privacy_safe_fields():
    record = usefulness_mark({"run_id": "RUN-observed", "mark": "helped", "text": "must-not-survive"})

    assert record == {"run_id": "RUN-observed", "mark": "helped"}
    assert set(record) == USEFULNESS_MARK_FIELDS


def test_usefulness_mark_rejects_free_text_as_run_id():
    assert not valid_usefulness_mark({"run_id": "secret task context", "mark": "helped"})
