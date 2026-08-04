# Telemetry

Telemetry measures one operator's real use of `ldw`; it is not a product-market benchmark and does not optimize tool behavior.

## Safe fields

Every event contains exactly the fields in `SAFE_FIELDS`: `tool`, `input_bytes`, `output_bytes`, `latency_ms`, `status`, `fallback_used`, `context_reduction`, `run_id`, and `error_code`. Events never contain source code, log bodies, prompts, secrets, provider responses, paths, or timestamps. `context_reduction` is `null` unless a `context pack` call in context mode supplied observable candidate sizes.

`error_code` is the first public generic code from the result's `errors`, or, when there is no error, the first public generic code from `warnings`; otherwise it is `null`. It is always one known code or `null`, never an empty string. Telemetry never copies error or warning details, text, resolved addresses, byte limits, raw model responses, or any other accompanying values. Records written before TEL-04 are read as `error_code: null` without rewriting the append-only journal.

Manual usefulness is a separate record type and does not expand `SAFE_FIELDS`. `ldw telemetry mark <run_id> <helped|not_helped|unclear>` appends exactly `run_id` and `mark`; free text, task context, paths, and provider data are not accepted or stored.

## Append-only journal

The CLI appends canonical JSON records to `.repo_index/ldw_sessions/YYYY-MM-DD.jsonl`. The date lives in the partition name so it does not expand either record type. Telemetry events and usefulness marks both use append mode and never truncate or mutate an existing record. Generated journal data is ignored by Git. Calls made by pytest are excluded from automatic real-session telemetry unless a telemetry test explicitly opts in; an explicit `telemetry mark` command remains the requested write itself. If automatic telemetry is unavailable, the original evidence result remains unchanged and the CLI emits only the generic `telemetry_write_failed` diagnostic to stderr. A failed manual mark remains visibly partial and is not reported as recorded.

## Summary

`ldw telemetry summary` reads the date partitions and returns total input/output bytes, measured context-mode calls and average context reduction, fallback count and ratio, evidence/report automation calls, `error_code_counts`, and a separate `usefulness` aggregate. `error_code_counts` contains counts for observed non-null known codes in the selected period; events with `error_code: null` are omitted from that breakdown. Usefulness counts and ratios use the latest appended mark for each `run_id`; `mark_records` retains the full append-only history while `marked_runs` is the denominator for `helped`, `not_helped`, and `unclear`. Optional `--from-date` and `--to-date` filters use ISO dates. The summary reads the journal before its own automatic event is appended, so the current summary call appears only in the next summary.

Wave 2 does not expand `SAFE_FIELDS`. Detailed candidate counts, byte volumes, exclusion counts, sensitive blocks, expansion results, and lineage completeness live in the command output and sanitized acceptance evaluator rather than the production journal. Repository identifiers, paths, raw contents, prompts, and provider data are not added to telemetry. Operator time, raw-reread rate, and time-to-actionable-context remain `NOT MEASURED` until directly observed.
