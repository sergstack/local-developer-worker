# Local Ollama advisory microbenchmark — 2026-08-28

## Status: transport observation only

Five synthetic, read-only advisory calls were made to local `qwen3:8b` through
the loopback-verified `ldw ollama advise` boundary. No repository, source,
prompt text, model envelope, or model response was retained. Each call produced
a schema-validated advisory result.

| Observation | Result |
| --- | ---: |
| Completed calls | 5 / 5 |
| End-to-end local advisory latency | 1,845–2,386 ms |
| Median local advisory latency | 2,064 ms |
| Raw response retained | false for all calls |
| Local runtime verified | true for all calls |

For orientation only, an unrelated prior `ldw codex run` recorded 45,688 ms,
184,764 input tokens, and 1,866 output tokens. It is not a matched control and
is deliberately not used to calculate a saving.

## Interpretation

This establishes that the local adapter is operational and has an approximately
two-second marginal cost for a short request on this machine. It does **not**
establish task quality, development-speed improvement, Codex-token savings, or
context improvement. No task class receives `PERMIT` from this microbenchmark.

The only candidate class for a later matched study is high-volume,
`terminal_deterministic` batch triage with a deterministic verifier. One-off
reviews, debugging, design, generated changes, and any task needing Codex to
judge the local result remain denied by the study contract.
