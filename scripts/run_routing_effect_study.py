from __future__ import annotations

import argparse
import json
from pathlib import Path

from local_developer_worker.routing_effect_study import analyze_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a privacy-safe paired Adaptive Routing effect-study manifest.")
    parser.add_argument("manifest", type=Path, help="sanitized JSON manifest; this command never executes Codex")
    args = parser.parse_args()
    print(json.dumps(analyze_manifest(json.loads(args.manifest.read_text())), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
