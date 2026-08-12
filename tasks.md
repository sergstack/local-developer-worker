# Tasks

## Preparation

- [x] Synchronize clean `main` with `origin/main` and record baseline.
- [x] Audit all transport, verifier, locality, CLI, runtime, internal, and test call sites.
- [x] Classify enforcement gap separately from production exposure.
- [x] Create `codex/pb4-04-transport-verifier-enforcement`.

## Scope lock

- Allowed files: `SPEC.md`, `plan.md`, `tasks.md`, `benchmarks/task_manifest.json` for deterministic changed-file size synchronization, `src/local_developer_worker/{policy.py,stage_b_cluster.py}`, `tests/stage_b/conftest.py`, directly affected tests under `tests/stage_b/`, `docs/gate_registry.json`, and `docs/tool-contracts.md`.
- Forbidden files: public schemas, routing/model policy values, PB4-03/Wave 2 semantics, dependencies, global configuration, secrets, `.repo_index/**`, migrations, and unrelated runtime/docs.
- Allowed actions: bounded edits, deterministic local tests/checks, commit, push, PR, merge, and post-merge verification authorized by the owner.
- Forbidden actions: provider/model calls, public verifier injection, automatic-routing change, production deployment, force push, protection bypass, and unrelated refactor.
- Public behavior rule: custom transport no longer bypasses canonical locality verification; all output schemas and other behavior remain unchanged.

## Implementation

- [x] Add pre-fix custom-transport bypass regression.
- [x] Add deterministic synthetic local Ollama process evidence for Stage B tests.
- [x] Remove `runtime_verifier=None` selection from `log_cluster`.
- [x] Verify custom transport cannot run before canonical verification passes.
- [x] Verify a canonically verified test runtime permits exactly one custom transport call.
- [x] Register `PB4-04-CUSTOM-TRANSPORT-VERIFIER-BYPASS` with separate production-exposure classification.

## Validation

- [x] Observe the pre-fix regression failure through `ldw test parse`.
- [x] Pass focused PB4-04 and production-path tests.
- [x] Pass affected PB4 and Stage B regression.
- [x] Pass full repository regression through `ldw test parse`.
- [x] Pass schema, fixture, release-gate, secret, compile, and diff checks.
- [x] Complete PB4-04-R1–R8 traceability, Security Judge, Diff Judge, and acceptance check.
- [ ] Verify merged `main` with the required bypass/negative/smoke checks.

## Acceptance mapping

- PB4-04-R1 — PASS: `stage_b_cluster.log_cluster`; custom transport uses the same guarded call.
- PB4-04-R2 — PASS: `test_pb4_04_custom_transport_cannot_skip_unverified_runtime`; unverified runtime is `policy_blocked`.
- PB4-04-R3 — PASS: the same regression proves transport calls remain zero until verification passes.
- PB4-04-R4 — PASS: `test_pb2_03_pipeline_uses_policy_config_and_existing_gate_functions`; verified runtime permits exactly one call.
- PB4-04-R5 — PASS: `tests/stage_b/conftest.py` supplies deterministic process observations without model calls.
- PB4-04-R6 — PASS: `log_cluster` exposes no verifier argument; the test seam is private `_PROCESS_RUNNER` lookup.
- PB4-04-R7 — PASS: existing SSH/socat/proxy/unverified tests plus production-path SSH regression.
- PB4-04-R8 — PASS: bounded-assurance test and registry preserve `physical_inference_locality: not_provable`.

## Forbidden actions

- Do not expose a verifier or verifier-disable argument on `log_cluster` or `log_process`.
- Do not invoke a model/provider or change routing/model configuration.
- Do not alter schemas, PB4-03, Wave 2, repo-index, Handoff, Documentation services, or unrelated code.
- Do not bypass GitHub gates or push directly to `main`.

## Documentation

- [x] Add only the confirmed corrective-defect evidence to PB4-04 governance.
- [x] Update only the locality contract sentence affected by transport-independent enforcement.
