import json
from pathlib import Path

from local_developer_worker.tools import context_pack


def test_fixed_code_slice_corpus_reduces_context_without_losing_required_fragments(tmp_path):
    root = Path(__file__).parents[2]
    corpus = json.loads((root / "fixtures" / "context_slices" / "reference_corpus.json").read_text())
    assert corpus["frozen"] is True
    reductions = []
    for case in corpus["cases"]:
        source_path = tmp_path / case["path"]
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(case["source"])
        data = context_pack({"repository_root": str(tmp_path), "files": [{"path": case["path"], "size_bytes": source_path.stat().st_size}], "target_files": [case["path"]], "target_symbols": [case["target_symbol"]]})["data"]
        slice_ = data["source_slices"][0]
        assert slice_["mode"] == "structural_slice"
        assert all(fragment in slice_["content"] for fragment in case["required_fragments"])
        reductions.append(1 - slice_["slice_bytes"] / source_path.stat().st_size)
    assert min(reductions) >= 0.5
