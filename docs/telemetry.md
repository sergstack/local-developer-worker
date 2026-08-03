# Telemetry

Telemetry measures one operator's real use of `ldw`; it is not a product-market benchmark and does not optimize tool behavior.

## Safe fields

Every event contains exactly the fields in `SAFE_FIELDS`: `tool`, `input_bytes`, `output_bytes`, `latency_ms`, `status`, `fallback_used`, `context_reduction`, and `run_id`. Events never contain source code, log bodies, prompts, secrets, provider responses, paths, or timestamps. `context_reduction` is `null` unless a `context pack` call in context mode supplied observable candidate sizes.

## Append-only journal

The CLI appends one canonical JSON event to `.repo_index/ldw_sessions/YYYY-MM-DD.jsonl`. The date lives in the partition name so it does not expand `SAFE_FIELDS`. Journal writes use append mode and never truncate an existing partition. Generated journal data is ignored by Git. Calls made by pytest are excluded from the real-session journal unless a telemetry test explicitly opts in. If the journal is unavailable, the original evidence result remains unchanged and the CLI emits only the generic `telemetry_write_failed` diagnostic to stderr.

## Summary

`ldw telemetry summary` reads the date partitions and returns total input/output bytes, measured context-mode calls and average context reduction, fallback count and ratio, and evidence/report automation calls. Optional `--from-date` and `--to-date` filters use ISO dates. The summary reads the journal before its own event is appended, so the current summary call appears only in the next summary.
