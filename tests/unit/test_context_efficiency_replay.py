import json
from pathlib import Path

import pytest

from local_developer_worker.context_efficiency_replay import analyze_replay


def test_dry_replay_is_bounded_and_cannot_promote():
    data = json.loads((Path(__file__).parents[2] / "fixtures/context_efficiency_replay/dry_run_manifest.json").read_text())
    result = analyze_replay(data)
    assert result["verdict"] == "REVISE"
    assert result["provider_calls"] is False
    assert result["task_success_regression"] is False


def test_replay_requires_shared_environment_budget_timeout_and_verifier():
    data = json.loads((Path(__file__).parents[2] / "fixtures/context_efficiency_replay/dry_run_manifest.json").read_text())
    del data["pairs"][0]["verifier_id"]
    with pytest.raises(ValueError, match="invalid_replay_pair"):
        analyze_replay(data)
