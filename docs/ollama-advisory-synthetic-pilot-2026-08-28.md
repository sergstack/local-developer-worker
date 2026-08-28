# Local Ollama terminal-triage synthetic pilot — 2026-08-28

## Verdict: technically suitable; not a production promotion

Five frozen synthetic batch-triage pairs were run under the same minimal
read-only model instruction and an identical deterministic marker verifier.
Control used Codex (`gpt-5.6-luna`, low effort); candidate used local
`qwen3:8b` through `ldw ollama advise`. The candidate did not invoke Codex.

Only opaque pair IDs and aggregate measurements are retained. Prompt text,
ticket text, assistant text, provider output, tool arguments, and transcript
events were discarded after the verifier ran.

| Measure | Control | Local Ollama candidate | Matched median delta |
| --- | ---: | ---: | ---: |
| Accepted pairs | 5 / 5 | 5 / 5 | no regression |
| End-to-end latency | 3,851–5,139 ms | 1,764–1,967 ms | -54.1937% |
| Codex provider tokens | 16,824–16,826 per pair | 0 | -100.0000% |
| Bytes presented to Codex | observed control task input | 0 | -100.0000% |

The local model’s own token counts were not observed by the safe adapter and
are not represented as zero or combined with Codex tokens.

## What this proves

For this corpus, a local model can replace Codex for a terminal,
schema-bounded batch-triage step when all of the following hold:

1. the output has a fixed, small shape;
2. a deterministic verifier can reject every missing required classification;
3. no Codex semantic review is required after the local result; and
4. the result is consumed as a work queue or another non-authoritative
   read-only artifact.

## What it does not prove

The cases are synthetic, so the study contract records
`evidence_status: synthetic` and deliberately returns `INSUFFICIENT_EVIDENCE`
instead of production `PERMIT`, despite all arithmetic gates being met. It does
not establish performance or task quality for real repository work, code
review, debugging, architecture, or generated modifications.
