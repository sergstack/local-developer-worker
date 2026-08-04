from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from .contracts import canonical_json
from .telemetry import normalize_telemetry_event, valid_session_record, valid_telemetry_event, valid_usefulness_mark

DEFAULT_ROOT = Path(__file__).parents[2] / ".repo_index" / "ldw_sessions"


def session_root(value: str | Path | None = None) -> Path:
    configured = value or os.environ.get("LDW_SESSION_LOG_DIR")
    return Path(configured or DEFAULT_ROOT).resolve(strict=False)


def append_event(event: dict[str, Any], root: str | Path | None = None, *, event_date: date | None = None) -> Path:
    if not valid_telemetry_event(event) and not valid_usefulness_mark(event):
        raise ValueError("invalid session record")
    destination = session_root(root)
    destination.mkdir(parents=True, exist_ok=True)
    partition = destination / f"{(event_date or date.today()).isoformat()}.jsonl"
    if partition.is_symlink():
        raise OSError("telemetry partition cannot be a symlink")
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(partition, flags, 0o600)
    try:
        payload = (canonical_json(event) + "\n").encode("utf-8")
        if os.write(descriptor, payload) != len(payload):
            raise OSError("incomplete telemetry append")
    finally:
        os.close(descriptor)
    return partition


def iter_records(root: str | Path | None = None, *, date_from: str | None = None, date_to: str | None = None) -> tuple[list[dict[str, Any]], int]:
    start = date.fromisoformat(date_from) if date_from else None
    end = date.fromisoformat(date_to) if date_to else None
    if start and end and start > end:
        raise ValueError("date_from must be on or before date_to")
    records: list[dict[str, Any]] = []
    invalid = 0
    source = session_root(root)
    if not source.is_dir():
        return records, invalid
    for path in sorted(source.glob("????-??-??.jsonl")):
        if path.is_symlink():
            invalid += 1
            continue
        try:
            partition_date = date.fromisoformat(path.stem)
        except ValueError:
            invalid += 1
            continue
        if start and partition_date < start or end and partition_date > end:
            continue
        try:
            lines: Iterable[str] = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            invalid += 1
            continue
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                invalid += 1
                continue
            if not valid_session_record(event):
                invalid += 1
                continue
            records.append(normalize_telemetry_event(event) or event)
    return records, invalid


def iter_events(root: str | Path | None = None, *, date_from: str | None = None, date_to: str | None = None) -> tuple[list[dict[str, Any]], int]:
    records, invalid = iter_records(root, date_from=date_from, date_to=date_to)
    return [record for record in records if valid_telemetry_event(record)], invalid
