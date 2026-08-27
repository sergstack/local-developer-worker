import json
from pathlib import Path

from local_developer_worker.tools import context_pack


def test_fixed_progressive_expansion_corpus_is_bounded_and_delta_only(tmp_path):
    root = Path(__file__).parents[2]
    corpus = json.loads((root / "fixtures" / "context_expansion" / "reference_corpus.json").read_text())
    assert corpus["frozen"] is True
    for case in corpus["cases"]:
        initial = context_pack({
            "repository_root": str(tmp_path), "files": case["files"],
            "target_files": case["target_files"], "max_context_files": case["max_context_files"],
        })
        current = initial
        for request in case["expansions"]:
            output = context_pack({
                "mode": "expand", "repository_root": str(tmp_path),
                "previous_run_id": current["run_id"], "previous_package": current,
                "requested_paths": request["requested_paths"], "reason": request["reason"],
                "files": case["files"], "max_context_files": case["max_context_files"],
                "max_expansion_depth": case.get("max_expansion_depth", 2),
            })
            if request.get("expected_error"):
                assert output["errors"][0]["code"] == request["expected_error"]
                break
            data = output["data"]
            assert {item["path"] for item in data["added_files"]}.isdisjoint(
                {item["path"] for item in data["reused_files"]}
            )
            current = output
        if current is not initial:
            assert current["data"]["metrics"]["total_context_bytes"] == case["expected_total_bytes"]
        else:
            assert current["data"]["metrics"]["initial_pack_bytes"] == case["expected_total_bytes"]
