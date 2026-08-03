from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

root = Path(__file__).parents[1] / "schemas"
for schema_path in sorted(root.glob("*.schema.json")):
    Draft202012Validator.check_schema(json.loads(schema_path.read_text()))

portfolio_schema = json.loads((root / "portfolio_item.schema.json").read_text())
registry = json.loads((root.parent / "docs" / "gate_registry.json").read_text())
assert registry["schema_version"] == "1.0.0"
assert len(registry["items"]) == 20
for item in registry["items"]:
    Draft202012Validator(portfolio_schema).validate(item)

print(f"validated {len(list(root.glob('*.schema.json')))} schemas and {len(registry['items'])} portfolio items")
