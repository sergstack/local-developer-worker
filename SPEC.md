# SPEC

## Goal

Build and execute the Stage B Phase 1 regression gate before any production log-clustering code is written. The portfolio contains exactly 10 objects: `POLICY-01`, `REF-01`, `GATE-01` through `GATE-07`, and `NR-01`.

## Current state

- Stage A is merged and accepted at `main` commit `5a3d146`.
- `policy.toml` denies network access and keeps `[semantic].enabled = false`, but does not document or enforce the approved loopback-only inference exemption.
- No Stage B reference corpus, semantic-group schema, gate evaluator, Phase 1 registry, or reconciliation report exists.
- `docs/stage-b-entry-gate.md` defines seven required regression properties but contains no executable Phase 1 evidence.

## Requirements

- Complete `POLICY-01` first: add the exact approved comment above `network_access = false`; resolve the configured inference endpoint host; permit only addresses that resolve exclusively to loopback; reject `0.0.0.0`, non-loopback IPs, mixed DNS results, resolution failures, and external hosts before any network call with `policy_blocked` and `non_loopback_inference_endpoint`.
- Include the endpoint rejection and sanitized inference-payload checks in `GATE-04`, not a separate gate. Unit and integration tests must prove no network call is attempted for rejected endpoints.
- Complete `REF-01` second: add at least 30 sanitized log fragments derived from repository test/CI patterns, with explicit ground truth for grouping, separation, and accounted exclusions.
- Keep benchmark/model probing separate from the gated validator. Gate logic must be deterministic and testable with mocked candidate responses; any optional real Ollama probe must use the same loopback guard and sanitized payload.
- Implement executable evidence for `GATE-01` source-span recall, `GATE-02` zero invented sources, `GATE-03` deterministic fallback, `GATE-04` privacy plus loopback enforcement, `GATE-05` model-derived labeling, `GATE-06` confidence bounds, `GATE-07` unchanged Stage A reports, and `NR-01` deterministic `needs_review` on path/extension disagreement.
- Define and validate a `semantic_group` JSON Schema. Observed Stage A events remain `origin = observed`; semantic groups use `origin = model-derived`.
- Add a separate 10-object Phase 1 registry and deterministic portfolio runner. Every object must have a status and exact evidence; `POLICY-01` starts `ready`, not `waiting_for_owner`; the final summary must reconcile registry, fixtures, schemas, tests, and observed checks.

## Constraints

- Do not enable `[semantic]`; do not implement production clustering, routing, daemon behavior, embeddings, automatic edits, or Phase 2.
- Do not relax `network_access = false` for external traffic and do not treat a textual exemption as enforcement.
- Use only Python 3.12 standard library plus existing dev dependencies. Do not add runtime or dev dependencies.
- Model output is untrusted candidate data. Confidence alone cannot suppress deterministic review.
- Preserve all Stage A behavior and SA-01 through SA-16. `tests/integration/test_stage_a_safety_matrix.py` remains unchanged.
- Do not push, open a PR, merge, or change remotes without separate authorization.

## Acceptance criteria

- The Phase 1 registry contains exactly the 10 required unique IDs; no item is `not_started` without an explicit explanation.
- `policy.toml` changes only by the approved loopback comment, with `[semantic].enabled = false` unchanged.
- Tests prove `127.0.0.1`, `::1`, and strictly loopback-resolving `localhost` are accepted; `0.0.0.0`, external IP/host, mixed results, and resolution failure are rejected before I/O with the required status and error code.
- REF-01 contains at least 30 sanitized fragments and machine-readable grouping/separation ground truth.
- GATE-01 through GATE-07 and NR-01 have executable tests linked from the registry; the Stage A safety matrix has zero regressions.
- Schema validation includes `semantic_group`; fixture validation includes REF-01; secret scan passes.
- Test status is established through `ldw test parse`; the final Phase 1 portfolio summary reports all 10 items, reconciliation results, observed checks, missing checks, next action, and `phase_1_complete` or `phase_1_partial`.

## Risks

- DNS names may resolve to mixed loopback/non-loopback addresses; fail closed rather than accepting one safe result.
- A gate harness can accidentally become production clustering code; keep it limited to validation, fallback, sanitization, and evidence reconciliation.
- Sanitized fixtures can drift from their expected group IDs or source spans; validate both directions.
- Direct pytest return-code handling would violate the accepted test-status rule; route observed runner output through `ldw test parse`.
