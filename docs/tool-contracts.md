# Tool contracts

Every command consumes one JSON object and returns a `ToolResult` v1.0.0. Tool failures use a visible status (`partial`, `unsupported`, `invalid_input`, `policy_blocked`, `timeout`, or `internal_error`) rather than an empty success response. Source-linked fields include a source identifier, raw SHA-256 and source range when applicable.

`ldw doctor` includes `data.test_status_reminder`, which directs callers to establish pass/fail through `ldw test parse` rather than interpreting runner output directly.

`ldw log parse` preserves one record per input line. `ldw log cluster` accepts only parsed log events and requires both semantic policy gates before using the configured loopback endpoint and model; it emits normalized `model-derived` groups or an honest observed-event fallback, never a raw model response. `ldw log process` runs Stage A on raw text and sends only valid observed parsed events to `log cluster` when the policy and routing threshold permit it; it records semantic attempt, acceptance, fallback, and one source-accounting record per Stage A event. `ldw test parse` only reports observed outcomes. `ldw git facts` runs read-only Git commands. `ldw files inventory` records paths and metadata without emitting sensitive contents. Optional `semantic_candidates` remain separate from observed files, commands, and tests.

`ldw context pack` payload contract `2.0.0` requires an explicit allowed repository root at the CLI boundary. Each included path has a selection reason, evidence source, and explicit/deterministic/candidate/unknown relevance status; each considered exclusion has a controlled reason and policy rule. `mode=expand` requires the previous full ToolResult and matching run ID, adds only bounded requests, and repeats root, symlink, sensitive, ignored, binary, generated, and limit checks. Legacy context keys remain readable.

`ldw evidence build` payload contract `2.0.0` preserves only supplied evidence with applicable source tool/run/path/event/test/Git lineage and controlled origins. Test status authority belongs only to `ldw test parse`; Git authority belongs to `ldw git facts` or explicit user-provided evidence; model groups remain candidates. Missing tests, questions, and next bounded action stay visible in resumable state. Legacy evidence keys remain readable.

`related_test` matching is intentionally limited to relative `src/` and `tests/` paths.

`ldw telemetry summary` reads privacy-safe local session events. `ldw portfolio verify` reconciles all declared gate tests and action artifacts without stopping after an item failure; `--only ID` resumes one item while preserving 20 output rows. `ldw portfolio status` reports saved evidence and marks completed evidence stale when the commit or workspace fingerprint changes.

`inference_endpoint_policy` returns a normal `ToolResult`; any non-loopback or unresolved inference endpoint returns `policy_blocked` with `non_loopback_inference_endpoint`. `guarded_inference_call` pins accepted calls to the validated loopback IP before invoking a supplied transport. The production clustering command reuses these Phase 1 controls rather than implementing a second endpoint validator.
