# Tasks

## Preparation

- [x] Confirm remote `main` merge commit and create `codex/stage-b-entry-gate` directly from `5a3d146`.
- [x] Read the canonical Phase 1 brief, `AGENTS.md`, Stage B entry gate, policy, contracts, schemas, and existing tests.
- [x] Replace Stage A execution artifacts with the bounded Phase 1 specification and plan.

## Scope lock

- Allowed files: `SPEC.md`, `plan.md`, `tasks.md`, `policy.toml`, focused Phase 1 source modules/scripts, Phase 1 schemas/registry/docs, `fixtures/stage_b/`, fixture/schema validators, new focused tests, and concise affected README/tool-contract text.
- Forbidden files: `tests/integration/test_stage_a_safety_matrix.py`, Stage A fixture contents, generated benchmark outputs, `.repo_index` state as source evidence, Git remotes, and unrelated project files.
- Allowed actions: local reads/writes, deterministic DNS mocking, loopback-only optional probe after guard completion, local validation, and local commits only when separately requested.
- Forbidden actions: external/non-loopback calls, production clustering, semantic enablement, Phase 2, dependencies, daemon/embeddings, push/PR/merge, destructive Git, and model-derived facts represented as observed.
- Public behavior may add a reusable fail-closed endpoint-policy result and Phase 1 validation scripts; existing Stage A CLI behavior must not change.

## Implementation

- [x] Add the exact approved loopback exemption comment to `policy.toml` without changing any value.
- [x] Implement endpoint host parsing, DNS resolution, and strict all-addresses-loopback enforcement.
- [x] Return `policy_blocked` with `non_loopback_inference_endpoint` before any network call for rejected endpoints.
- [x] Add POLICY-01/GATE-04 tests for IPv4/IPv6 loopback, localhost, wildcard, external, mixed, and resolution-failure cases plus no-I/O proof.
- [x] Create REF-01 with at least 30 sanitized log fragments and explicit grouping/separation/exclusion ground truth.
- [x] Extend fixture validation for REF-01 cardinality, sanitization, IDs, and bidirectional ground-truth consistency.
- [x] Add the `semantic_group` schema and register it in schema validation.
- [x] Implement inference-payload allowlisting from sanitized Stage A events.
- [x] Implement candidate source-span, recall, origin, confidence, and deterministic fallback validation.
- [x] Implement NR-01 path/extension disagreement logic independent of model confidence.
- [x] Add exact GATE-01–06 and NR-01 tests against REF-01 and adversarial candidate responses.
- [x] Add GATE-07 evidence that runs the unchanged Stage A safety matrix and checks its source hash against `5a3d146`.
- [x] Add the exact 10-object Phase 1 registry with POLICY-01 initially `ready` and linked evidence nodes.
- [x] Add a non-blocking Phase 1 runner that routes pytest output through `ldw test parse` and emits the required reconciled summary.

## Validation

- [x] Establish focused and full pytest status through `ldw test parse`.
- [x] Run compile, schema, fixture, secret, deterministic-rerun, policy-diff, and registry reconciliation checks.
- [x] Confirm `[semantic].enabled = false`, no production clustering entrypoint, no external network attempt, and no Stage A safety-matrix diff.
- [x] Run the acceptance check requirement by requirement against `SPEC.md`.

## Acceptance mapping

- POLICY-01 tasks and GATE-04 tests prove the loopback exemption is architectural rather than advisory.
- REF-01 tasks and fixture validation prove the ≥30 sanitized reference set and ground truth.
- Schema/gate/NR tests prove GATE-01–06 and NR-01; unchanged Stage A matrix plus parsed results prove GATE-07.
- Registry/runner tasks prove 10-object status, non-blocking evidence, reconciliation, and resumability.
- Final validation proves Phase 2 remains closed and Stage A is unchanged.

## Forbidden actions

- Do not enable `[semantic]` or implement production clustering/model routing.
- Do not make non-loopback calls, even for validation.
- Do not edit `tests/integration/test_stage_a_safety_matrix.py`.
- Do not push, open a PR, merge, fetch again, pull, or mutate remotes without separate authorization.

## Documentation

- [x] Document the Phase 1 registry/runner, loopback-only policy enforcement, and the distinction between optional benchmark probing and gated validation.
- [x] Update task checkboxes only after their evidence is observed.
