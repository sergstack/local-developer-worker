# Context Efficiency live aggregate capture (#37)

`build_replay_manifest` is an internal, pure conversion boundary for an
owner-authorized #37 matched replay. It accepts two supplied **aggregate** arm
records per frozen coding task and produces the existing v1.1 replay manifest
for `analyze_replay`.

It accepts only opaque evidence IDs and aggregate values: context bytes,
estimated/observed input-token counts, selected-file and expansion counts, tool
calls, latency, task acceptance, and optional provider cost. It rejects unknown
fields, including transcripts, prompts, tool arguments, file contents, and raw
provider responses. It does not read or write files, start agents, invoke a
provider, run a verifier, or persist data.

For every pair, both arms must name the same frozen task, environment revision,
budget, timeout, and verifier. The caller retains the source records and passes
the returned manifest to `analyze_replay`, which still requires observed status,
an owner approval ID, positive thresholds for all three promotion metrics, and
no task-success regression before it can return `PASS`.

This module is preparation, not live evidence. It does not freeze a corpus,
authorize a write-capable agent, choose materiality thresholds, or establish
any Context Efficiency benefit.

## Diagnostic extension v1.2

`summarize_replay_diagnostics` accepts the v1.2 form of the same supplied
aggregate study. In addition to the v1.1 fields, each arm has only aggregate
`expansion_bytes`, `compaction_count`, `reread_after_compaction_count`,
`preliminary_attempt_count`, and allowlisted reason codes. It returns a
diagnostic-only comparison and cannot be supplied to `analyze_replay` as a
promotion manifest. Historical v1.1 evidence and all of its acceptance
semantics remain unchanged.
