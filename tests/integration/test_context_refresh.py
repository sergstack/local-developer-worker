import json
from pathlib import Path

from local_developer_worker.tools import context_pack, context_refresh


def test_failure_refresh_localizes_observed_path_and_bounds_retries(tmp_path):
    initial = context_pack({"repository_root": str(tmp_path), "files": [{"path": "src/app.py", "size_bytes": 100}, {"path": "src/config.py", "size_bytes": 80}], "target_files": ["src/app.py", "src/config.py"]})
    localized = context_refresh({"previous_run_id": initial["run_id"], "previous_package": initial, "observed_failures": [{"event_id": "EV-1", "source_path": "src/app.py", "asserted_root_cause": "ignored"}]})
    assert localized["data"]["refresh_mode"] == "localized_delta"
    assert localized["data"]["inferred_root_cause"] is None
    assert [item["path"] for item in localized["data"]["refresh_files"]] == ["src/app.py"]
    fallback = context_refresh({"previous_run_id": initial["run_id"], "previous_package": initial, "observed_failures": [{"source_path": "src/app.py"}, {"source_path": "src/config.py"}]})
    assert fallback["data"]["refresh_mode"] == "whole_pack_fallback"
    bounded = context_refresh({"previous_run_id": initial["run_id"], "previous_package": initial, "observed_failures": [], "prior_refreshes": 1})
    assert bounded["errors"][0]["code"] == "refresh_limit_reached"


def test_fixed_failure_refresh_corpus_preserves_observed_evidence_boundaries(tmp_path):
    corpus = json.loads((Path(__file__).parents[2] / "fixtures" / "context_refresh" / "reference_corpus.json").read_text())
    assert corpus["frozen"] is True
    initial = context_pack({"repository_root": str(tmp_path), "files": [{"path": "src/app.py", "size_bytes": 100}, {"path": "src/config.py", "size_bytes": 80}], "target_files": ["src/app.py", "src/config.py"]})
    for case in corpus["cases"]:
        output = context_refresh({"previous_run_id": initial["run_id"], "previous_package": initial, "observed_failures": case["failures"], "prior_refreshes": case.get("prior_refreshes", 0)})
        if "expected_error" in case:
            assert output["errors"][0]["code"] == case["expected_error"]
            continue
        data = output["data"]
        assert data["refresh_mode"] == case["expected_mode"]
        assert [item["path"] for item in data["refresh_files"]] == case["expected_paths"]
        assert data["inferred_root_cause"] is None
