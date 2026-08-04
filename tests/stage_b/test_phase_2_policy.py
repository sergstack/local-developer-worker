from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_pb2_02_semantic_runtime_configuration_comes_from_policy():
    with (ROOT / "policy.toml").open("rb") as handle:
        policy = tomllib.load(handle)

    assert policy["automatic"]["semantic_log_clustering"] is False
    assert policy["semantic"] == {
        "enabled": False,
        "code_artifact": "disabled",
        "model": "qwen3:4b",
        "endpoint": "http://127.0.0.1:11435/api/generate",
        "automatic_routing": False,
    }


def test_pb2_02_model_probe_has_no_endpoint_or_model_literal_defaults():
    source = (ROOT / "scripts" / "run_stage_b_model_probe.py").read_text()
    production_source = (ROOT / "src" / "local_developer_worker" / "stage_b_cluster.py").read_text()

    assert "127.0.0.1:11434" not in source
    assert 'default="qwen3:4b"' not in source
    assert "load_policy(args.policy_path)" in source
    assert "127.0.0.1:11434" not in production_source
    assert "qwen3:4b" not in production_source
    assert 'semantic.get("endpoint")' in production_source
    assert 'semantic.get("model")' in production_source


def test_pb2_05_governance_registry_contains_the_bounded_feature_without_sa17():
    import json

    registry = json.loads((ROOT / "docs" / "gate_registry.json").read_text())
    feature = next(item for item in registry["governed_features"] if item["id"] == "PB2-LOG-CLUSTERING")

    assert feature["command"] == "ldw log cluster"
    assert feature["default_enabled"] is False
    assert feature["capability"] == "[automatic].semantic_log_clustering"
    assert feature["code_artifact"] == "disabled"
    assert all(item["id"] != "SA-17" for item in registry["items"])
