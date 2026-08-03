# Tool contracts

Every command consumes one JSON object and returns a `ToolResult` v1.0.0. Tool failures use a visible status (`partial`, `unsupported`, `invalid_input`, `policy_blocked`, `timeout`, or `internal_error`) rather than an empty success response. Source-linked fields include a source identifier, raw SHA-256 and source range when applicable.

`ldw doctor` includes `data.test_status_reminder`, which directs callers to establish pass/fail through `ldw test parse` rather than interpreting runner output directly.

`ldw log parse` preserves one record per input line. `ldw log cluster` accepts only parsed log events and requires both semantic policy gates before using the configured loopback endpoint and model; it emits normalized `model-derived` groups or an honest observed-event fallback, never a raw model response. `ldw test parse` only reports observed outcomes. `ldw git facts` runs read-only Git commands. `ldw files inventory` records paths and metadata without emitting sensitive contents. `ldw evidence build`, `ldw context pack`, and `ldw report summarize` preserve explicit missing evidence and selection reasons. Optional `semantic_candidates` remain separate from observed files, commands, and tests.

`related_test` matching is intentionally limited to relative `src/` and `tests/` paths.

`ldw telemetry summary` reads privacy-safe local session events. `ldw portfolio verify` reconciles all declared gate tests and action artifacts without stopping after an item failure; `--only ID` resumes one item while preserving 20 output rows. `ldw portfolio status` reports saved evidence and marks completed evidence stale when the commit or workspace fingerprint changes.

`inference_endpoint_policy` returns a normal `ToolResult`; any non-loopback or unresolved inference endpoint returns `policy_blocked` with `non_loopback_inference_endpoint`. `guarded_inference_call` pins accepted calls to the validated loopback IP before invoking a supplied transport. The production clustering command reuses these Phase 1 controls rather than implementing a second endpoint validator.
