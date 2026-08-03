from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "1.0.0"
STATUSES = {"success", "partial", "unsupported", "invalid_input", "policy_blocked", "timeout", "internal_error"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class SourceReference:
    source: str
    raw_hash: str
    line_start: int | None = None
    line_end: int | None = None
    parse_status: str = "parsed"


@dataclass
class ToolResult:
    tool: str
    status: str
    input_manifest: dict[str, Any]
    data: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    run_id: str = ""
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        if self.status not in STATUSES:
            raise ValueError(f"invalid status: {self.status}")
        return asdict(self)


def manifest(source: str, raw: str | bytes) -> dict[str, Any]:
    raw_bytes = raw.encode("utf-8") if isinstance(raw, str) else raw
    return {"source": source, "size_bytes": len(raw_bytes), "sha256": sha256(raw_bytes)}


def result(tool: str, source: str, raw: str | bytes, data: dict[str, Any], *, status: str = "success", warnings: list[dict[str, Any]] | None = None, errors: list[dict[str, Any]] | None = None, started: float | None = None) -> dict[str, Any]:
    duration = round((time.perf_counter() - started) * 1000) if started is not None else 0
    input_manifest = manifest(source, raw)
    run_id = f"RUN-{sha256(canonical_json({'tool': tool, 'input': input_manifest}))[:16]}"
    return ToolResult(tool=tool, status=status, input_manifest=input_manifest, data=data, warnings=warnings or [], errors=errors or [], metrics={"duration_ms": duration, "input_items": 0, "output_items": len(data)}, run_id=run_id).to_dict()


def stable_hash(value: Any) -> str:
    return sha256(canonical_json(value))


def valid_tool_result(value: Any) -> bool:
    """Minimal runtime boundary for the published ToolResult contract."""
    if not isinstance(value, dict): return False
    required = {"schema_version", "tool", "run_id", "status", "input_manifest", "data", "warnings", "errors", "metrics"}
    if not required <= set(value) or value.get("schema_version") != SCHEMA_VERSION or value.get("status") not in STATUSES: return False
    manifest_value = value.get("input_manifest")
    return isinstance(manifest_value, dict) and {"source", "size_bytes", "sha256"} <= set(manifest_value) and isinstance(value.get("data"), dict) and isinstance(value.get("warnings"), list) and isinstance(value.get("errors"), list) and isinstance(value.get("metrics"), dict)
