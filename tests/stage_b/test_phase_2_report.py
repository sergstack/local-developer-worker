from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
BASELINE_WITHOUT_SEMANTIC = (
    '{"data":{"acceptance_evidence":{"content_hash":"PB2-GOLDEN"},"commands_observed":[],'
    '"files_changed":[],"missing_checks":[],"residual_risks":[],"rollback_facts":'
    '{"working_tree_clean":true},"summary":"Facts-only report generated from evidence package.",'
    '"tests_observed":[],"warnings":[]},"errors":[],"input_manifest":'
    '{"sha256":"282b7334dc47103844c8f020665e20bc277d1b39d25a83c1a3c7f5a25f2a29e6",'
    '"size_bytes":201,"source":"stdin"},"metrics":{"duration_ms":0,"input_items":0,'
    '"output_items":9},"run_id":"RUN-4931bdae5bd4c5c5","schema_version":"1.0.0",'
    '"status":"success","tool":"change_summarizer","warnings":[]}\n'
)


def _payload():
    return {
        "evidence_package": {
            "repository_state": {
                "changed_files": [],
                "command_evidence": [],
                "working_tree_clean": True,
            },
            "observed_test_results": [],
            "missing_evidence": [],
            "warnings": [],
            "content_hash": "PB2-GOLDEN",
        }
    }


def _run(payload):
    return subprocess.run(
        [sys.executable, "-m", "local_developer_worker.cli", "report", "summarize"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "LDW_TELEMETRY_DISABLED": "1"},
        check=False,
    )


def test_pb2_04_report_without_semantic_data_is_byte_identical_to_phase_1():
    completed = _run(_payload())

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout == BASELINE_WITHOUT_SEMANTIC


def test_pb2_04_report_keeps_semantic_candidates_separate_from_observed_facts():
    payload = _payload()
    payload["semantic_candidates"] = [{
        "group_id": "SG-SYNTHETIC",
        "pattern": "repeated synthetic failure",
        "classification": "synthetic_failure",
        "source_span": ["EV-000001"],
        "confidence": 0.8,
        "origin": "model-derived",
        "needs_review": False,
    }]

    output = json.loads(_run(payload).stdout)

    assert output["status"] == "success"
    assert output["data"]["semantic_candidates"] == payload["semantic_candidates"]
    assert output["data"]["tests_observed"] == []
    assert output["data"]["files_changed"] == []


def test_pb2_04_report_rejects_unlabeled_semantic_candidates():
    payload = _payload()
    payload["semantic_candidates"] = [{"origin": "observed"}]

    output = json.loads(_run(payload).stdout)

    assert output["status"] == "invalid_input"
    assert output["errors"] == [{"code": "invalid_semantic_candidates"}]


def test_pb2_04_report_rejects_malformed_semantic_candidate_types():
    payload = _payload()
    payload["semantic_candidates"] = [{
        "group_id": "SG-SYNTHETIC",
        "pattern": "synthetic",
        "classification": "synthetic_failure",
        "source_span": ["not-an-event-id"],
        "confidence": True,
        "origin": "model-derived",
        "needs_review": "false",
    }]

    output = json.loads(_run(payload).stdout)

    assert output["status"] == "invalid_input"
    assert output["errors"] == [{"code": "invalid_semantic_candidates"}]
