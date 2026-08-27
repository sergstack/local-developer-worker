# Context Efficiency synthetic replay check

`fixtures/context_efficiency_replay/synthetic_matched_replay_manifest.json` is a deterministic **dry-run** fixture for the #37 replay contract. It contains only opaque IDs and aggregate metrics; it never starts an agent, a provider, or a verifier.

The fixture verifies that the harness preserves matched task acceptance, tool calls, latency, explicit baseline/candidate revisions, and an adverse per-pair outlier. Its aggregate median shows lower context bytes, tool calls, and latency, while the third pair regresses on tool calls and latency. The unit test also turns that pair into a rejected candidate task and verifies that a hypothetical live manifest returns `STOP`.

This fixture is contract evidence only. Its `dry_run` mode always yields `REVISE`, so it cannot close #37 or establish coding-agent benefit. In particular, it does not provide observed execution, an owner-approved materiality threshold, provider cost, or real downstream acceptance. A real #37 study must use an owner-approved frozen corpus and retain the same per-pair evidence.
