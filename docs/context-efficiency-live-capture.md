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
