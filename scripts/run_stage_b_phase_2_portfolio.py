from __future__ import annotations

from local_developer_worker.contracts import canonical_json
from local_developer_worker.stage_b_phase_2_portfolio import run_phase_2_portfolio


def main() -> int:
    output = run_phase_2_portfolio()
    print(canonical_json(output))
    return 0 if output["portfolio_acceptance"] == "phase_2_complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
