#!/usr/bin/env python3
"""Render a deterministic local-Ollama advisory study from a sanitized manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from local_developer_worker.ollama_advisory_study import analyze_manifest


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: run_ollama_advisory_study.py MANIFEST.json", file=sys.stderr)
        return 2
    manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(analyze_manifest(manifest), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
