from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

root = Path(__file__).parents[1] / "schemas"
for schema_path in sorted(root.glob("*.schema.json")):
    Draft202012Validator.check_schema(json.loads(schema_path.read_text()))
print(f"validated {len(list(root.glob('*.schema.json')))} schemas")
