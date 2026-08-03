# Plan

## Missing inputs

- None. Global activation is explicitly owner-gated and may remain pending.

## Scope assumptions

- Canonical base is `origin/main` at `1e738256dfbd72fcac4386d8a3c9a0d776f3e6d9`.
- Existing context and evidence fields remain readable; new acceptance fields use an explicit Wave 2 contract version.
- Cross-repository checks are read-only and use explicit temporary policy inputs rather than global configuration changes.

## Affected files / areas

- `src/local_developer_worker/` context, evidence, policy-boundary, and telemetry integration.
- Public context/evidence schemas and migration documentation.
- `fixtures/wave2/`, a deterministic evaluator, and focused unit/contract/integration/security tests.
- README, tool contracts, governance registry, generated release gates, and an unapplied owner-gated AGENTS patch.

## Steps

1. Record the W2-00 baseline and lock allowed files, actions, public behavior, and validation.
2. Freeze a 15-case sanitized reference corpus with immutable expected critical files and safety expectations.
3. Extend context selection with explicit root validation, traceable inclusion/exclusion records, visible low-benefit/unsupported states, and deterministic metrics.
4. Add bounded expansion linked to a supplied previous package while preserving legacy context outputs.
5. Extend evidence packages with validated per-item lineage and resumable handoff state while preserving legacy inputs.
6. Add focused unit, contract, integration, security, deterministic, and resume tests.
7. Add the frozen evaluator and privacy-safe Wave 2 acceptance output.
8. Synchronize schemas, migration notes, README, tool contracts, governance registry, release gates, and the unapplied AGENTS patch.
9. Run focused checks, full validation, three-repository read-only smoke, and global CLI source-provenance checks.
10. Perform final acceptance review and prepare the owner package without staging or publishing changes.

## Dependencies

- Step 2 depends on Step 1.
- Steps 3–5 depend on Steps 1–2.
- Steps 6–7 depend on Steps 3–5.
- Step 8 depends on the public behavior established in Steps 3–7.
- Step 9 depends on Steps 6–8.
- Step 10 depends on all previous steps.

## Risks

- Existing tests rely on legacy keys and may reveal compatibility gaps.
- Real repositories may not expose enough safe deterministic signals for an eligible reduction measurement.
- Global editable installation provenance may prevent `globally active and accepted` status.

## Validation strategy

- Establish every pytest outcome through `ldw test parse`.
- Run focused tests after each bounded implementation group.
- Run schemas, fixtures, generated-document drift, secret scan, compilation, full pytest, frozen evaluator, deterministic reruns, and Git diff checks.
- Snapshot each real repository before and after smoke checks and verify no tracked or untracked state changes.

## Parallel work

- After the core contracts stabilize, reference evaluation, evidence-lineage checks, root/sensitive checks, documentation, and read-only repository discovery are independent.
