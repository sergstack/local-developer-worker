from __future__ import annotations

import argparse
from pathlib import Path

from local_developer_worker.portfolio import load_registry, render_release_gates

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "docs" / "release-gates.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Stage A gate document from the canonical registry")
    parser.add_argument("--check", action="store_true", help="fail if the committed document differs")
    args = parser.parse_args()
    rendered = render_release_gates(load_registry())
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != rendered:
            print("release gate document is out of date")
            return 1
        print("release gate document is current")
        return 0
    OUTPUT.write_text(rendered, encoding="utf-8")
    print("generated docs/release-gates.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
