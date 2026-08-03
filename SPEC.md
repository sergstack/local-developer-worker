# SPEC

## Goal

Implement Stage B Phase 2: a production `ldw log cluster` path that reuses the accepted Phase 1 payload validator, loopback guard, candidate evaluator, and deterministic fallback.

## Requirements

- PB2-01: apply the owner-approved SA-14 option (b). Network, edit, commit, merge, and deploy remain denied by default. Semantic authority remains default-off and may be enabled only for `[automatic].semantic_log_clustering`; `code_artifact` remains disabled.
- PB2-02: read `model = "qwen3:4b"` and `endpoint = "http://127.0.0.1:11435/api/generate"` only from the active policy. Production code has no 11434/model default.
- PB2-03: expose `ldw log cluster` for sanitized parsed events. Dispatch requires both semantic gates and uses `build_inference_payload`, `guarded_inference_call`, and `evaluate_candidate_response` without duplicating their security logic.
- PB2-04: add optional `semantic_candidates` to reports without mixing them into observed files, commands, or tests. Reports without semantic data remain byte-identical to the Phase 1 baseline.
- PB2-05: synchronize SA-01, schemas, governance, README, and tool contracts without creating SA-17.
- PB2-06: Stage A must remain 20/20 complete and Stage B Phase 1 10/10 complete.
- PB2-07: record one supervised production call on REF-01. A real response is mandatory; unavailable runtime means `waiting_for_input`. Invalid model candidates must produce honest fallback, never mock success.
- PB2-08: document disablement and the immutable status of historical model-derived evidence.

## Constraints

- Default `policy.toml` keeps both semantic gates false and all mutation/deploy capabilities false.
- Never enable `code_artifact`.
- Never emit or persist a raw model response, prompt, raw log, secret, or provider response in telemetry or evidence.
- Only loopback inference is permitted; the existing Phase 1 guard remains authoritative.
- No new dependencies, daemon, embeddings, automatic edits, commits, merges, deploys, or external-network authority.
- No push, PR, or merge without separate authorization.

## Acceptance criteria

- Phase 2 registry contains exactly PB2-01 through PB2-08 and its runner reports `phase_2_complete` only when all evidence and reconciliation checks pass.
- Every public command emits schema-valid ToolResult; `log cluster` is included in SA-01.
- Non-loopback endpoints and disabled capabilities block before transport.
- Success exposes only normalized model-derived groups; transport or validation failure exposes only deterministic observed fallback.
- Full tests, schemas, fixtures, secret scan, Stage A 20/20, Phase 1 10/10, and Phase 2 8/8 pass.
- Supervised evidence proves qwen3:4b responded on 11435; raw response storage remains false.

## Risks

- A model can return invented or duplicated source IDs; the accepted gate must reject them.
- Changes to the Stage A safety matrix can weaken legacy coverage; Phase 1 GATE-07 permits only the exact authorized `log cluster` delta.
- A policy override can enable clustering, but it must not grant unrelated semantic or mutation authority.
