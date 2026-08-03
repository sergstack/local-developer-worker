# Tool contracts

Every command consumes one JSON object and returns a `ToolResult` v1.0.0. Tool failures use a visible status (`partial`, `unsupported`, `invalid_input`, `policy_blocked`, `timeout`, or `internal_error`) rather than an empty success response. Source-linked fields include a source identifier, raw SHA-256 and source range when applicable.

`ldw log parse` preserves one record per input line. `ldw test parse` only reports observed outcomes. `ldw git facts` runs read-only Git commands. `ldw files inventory` records paths and metadata without emitting sensitive contents. `ldw evidence build`, `ldw context pack`, and `ldw report summarize` preserve explicit missing evidence and selection reasons.

`related_test` matching is intentionally limited to relative `src/` and `tests/` paths.
