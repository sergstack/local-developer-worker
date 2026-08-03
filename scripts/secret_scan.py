from __future__ import annotations

import re
from pathlib import Path

root = Path(__file__).parents[1]
pattern = re.compile(r"(?:AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----)")
matches = []
for path in root.rglob("*"):
    if not path.is_file() or any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
        continue
    try:
        if pattern.search(path.read_text(errors="ignore")):
            matches.append(str(path.relative_to(root)))
    except OSError:
        pass
if matches:
    raise SystemExit("secret-like material found: " + ", ".join(matches))
print("secret scan passed")
