from __future__ import annotations

import argparse
import json

from local_developer_worker.stage_b_portfolio import run_phase_1_portfolio


parser = argparse.ArgumentParser(description="Run the deterministic Stage B Phase 1 regression portfolio")
parser.add_argument("--timeout", type=int, default=120)
args = parser.parse_args()
print(json.dumps(run_phase_1_portfolio(timeout=args.timeout), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
