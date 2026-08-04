from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("pb4_mac_evaluator", ROOT / "scripts" / "run_pb4_03_evaluation.py")
assert SPEC and SPEC.loader
evaluator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluator)


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute safe PB4-03 aggregates without model calls.")
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text())
    if evidence.get("execution_status") != "COMPLETE" or evidence.get("attempted_runs") != 20 or len(evidence.get("runs", [])) != 20:
        raise ValueError("complete_twenty_run_evidence_required")
    aggregates = [evaluator.aggregate(model, [run for run in evidence["runs"] if run["model_requested"] == model]) for model in evidence["models"]]
    evidence["per_model"] = aggregates
    evidence["comparison"] = evaluator.comparison(aggregates)
    evaluator.write_output(args.evidence, evidence)
    print(json.dumps({"evidence": str(args.evidence), "model_calls_performed": 0, "per_model": aggregates, "comparison": evidence["comparison"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
