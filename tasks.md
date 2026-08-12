# Tasks

## Preparation

- [x] Align clean local `main` with `origin/main` and record baseline SHA.
- [x] Audit Wave 2, PB4-03, PB4-04, repo-index, handoff, and documentation-service claims against repository and merged PR evidence.
- [x] Create `codex/ldw-governance-closure`.

## Scope lock

- Allowed files: `SPEC.md`, `plan.md`, `tasks.md`, `policy.toml` for the corrected locality assurance comment, `benchmarks/task_manifest.json` for deterministic changed-file size synchronization, `src/local_developer_worker/{policy.py,stage_b_cluster.py,telemetry.py}`, directly affected tests under `tests/security/` and `tests/stage_b/`, and directly affected `docs/{wave-2-acceptance.md,wave-2-codex-integration.patch.md,pb4-03-owner-acceptance.md,stage-b-entry-gate.md,tool-contracts.md,gate_registry.json,release-gates.md}`.
- Forbidden files: secrets, `.env*`, `.repo_index/**`, external repositories, global configuration, unrelated runtime/modules, persistent data, migrations, deployment, and dependency manifests.
- Allowed actions: bounded edits, local deterministic tests/checks, generated release-gate synchronization, branch/commit/push/PR/merge/post-merge verification authorized by the owner.
- Forbidden actions: external model/provider calls, model pulls, automatic routing enablement, code-artifact enablement, force push, branch-protection bypass, production deployment, and speculative repo-index or service implementation.
- Public behavior rule: preserve existing output contracts; additive inference-assurance metadata and a fail-closed production locality guard are allowed by this SPEC.

## Implementation

- [x] Add negative tests proving loopback tunnel/proxy and unverifiable listeners do not reach transport.
- [x] Add positive tests for an observed local Ollama listener and explicit non-physical assurance metadata.
- [x] Implement local listener/process verification at the guarded inference boundary.
- [x] Preserve injected deterministic transports for tests without weakening the production CLI path.
- [x] Reconcile Wave 2 activation, PB4-03 completion, and PB4-04 control status.

## Validation

- [x] Observe the pre-fix locality test failure.
- [x] Pass focused security, Stage B, schema, registry, and documentation checks through the required parser where applicable.
- [x] Pass the relevant full regression through `ldw test parse`.
- [x] Run fixture/schema/release-gate generation checks, compilation, secret scan if available, and `git diff --check`.
- [x] Build an observed-facts evidence package and complete final diff review.
- [ ] Verify merged `main` and the bounded activation state.

## Acceptance mapping

- Governance accuracy: preparation tasks and status/documentation implementation task.
- PB4 locality security: locality tests, boundary implementation, and focused/full validation tasks.
- Scope preservation: scope lock, diff review, and repo-index/handoff no-change classifications.
- Delivery completion: commit, push, PR, checks, merge, and post-merge validation in the final plan step.

## Forbidden actions

- Do not call an external provider or invoke local model inference.
- Do not enable automatic semantic routing or code artifacts.
- Do not add dependencies or implement unconfirmed repo-index/handoff/documentation subsystems.
- Do not read or commit secret, raw provider, `.repo_index`, or machine-local evidence files.
- Do not bypass failing tests, required checks, or branch protection.

## Documentation

- [x] Replace stale Wave 2 pre-implementation and activation claims with current accepted/active behavior.
- [x] Document PB4-03 lifecycle evidence and PB4-04 assurance limits.
- [x] Regenerate `docs/release-gates.md` from the canonical registry.
- [x] Record repo-index and handoff/documentation as intentionally unchanged based on current evidence.
