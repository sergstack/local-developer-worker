from __future__ import annotations

import json
import tomllib
from pathlib import Path

from local_developer_worker.portfolio import render_release_gates


ROOT = Path(__file__).parents[2]


def _profile(name: str) -> dict:
    with (ROOT / "examples" / "policies" / f"{name}.toml").open("rb") as handle:
        return tomllib.load(handle)


def test_archived_profiles_are_explicit_only_blocked_and_non_mutating():
    for name, model in (("supervised_quality", "qwen3:8b"), ("supervised_fast", "gemma3:4b")):
        profile = _profile(name)
        semantic = profile["semantic"]
        assert profile["profile"] == name
        assert profile["activation_status"] == "blocked_dependency"
        assert profile["network_access"] is False
        assert all(profile[key] is False for key in ("automatic_edit", "automatic_commit", "automatic_merge", "production_deploy"))
        assert profile["automatic"]["semantic_log_clustering"] is True
        assert semantic == {
            "enabled": True,
            "code_artifact": "disabled",
            "model": model,
            "endpoint": "http://127.0.0.1:11435/api/generate",
            "contract_version": 2,
            "invocation": "explicit_manual_per_call",
            "automatic_routing": False,
            "model_fallback": "disabled",
            "temperature": 0,
            "think": False,
        }


def test_model_posture_records_selected_explicit_activation_without_automatic_routing():
    registry = json.loads((ROOT / "docs" / "gate_registry.json").read_text())
    posture = registry["stage_b_model_posture"]

    assert posture["status"] == "selected_and_supervised_active"
    assert posture["recommended_quality_model"]["value"] == "qwen3:8b"
    assert posture["configured_global_model"]["value"] == "qwen3:8b"
    assert posture["actually_invoked_model"]["value"] == "qwen3:8b"
    assert posture["activated_supervised_model"]["value"] == "qwen3:8b"
    assert posture["fast_challenger"] == {"value": "gemma3:4b", "classification": "HISTORICAL", "installed": False}
    assert posture["formal_winner"] == {"value": "not_established", "classification": "NOT ESTABLISHED"}
    assert posture["economic_winner"] == {"value": "not_measured", "classification": "NOT MEASURED"}
    assert posture["owner_decision"]["selected_option"] == "A"
    assert posture["supervised_explicit_activation"] == {
        "allowed": True,
        "active": True,
        "model": "qwen3:8b",
        "profile": "balanced",
        "invocation": "explicit_manual_per_call",
        "blockers": [],
    }
    assert posture["automatic_routing"] == {"allowed": False, "enabled": False}
    assert "activation" not in posture


def test_release_gate_render_preserves_wave2_and_adds_selected_model_posture():
    rendered = render_release_gates(json.loads((ROOT / "docs" / "gate_registry.json").read_text()))

    assert "## Wave 2 — Context and Evidence Layer" in rendered
    assert "## Stage B model posture" in rendered
    assert "Status: `selected_and_supervised_active`." in rendered
    assert "| configured_global_model | qwen3:8b | OBSERVED |" in rendered
    assert "| fast_challenger | gemma3:4b | HISTORICAL |" in rendered
    assert "Selected owner option: `A`." in rendered
    assert "Supervised explicit blockers: none." in rendered
    assert "Automatic routing allowed: `false`." in rendered
    assert "Automatic routing enabled: `false`." in rendered
