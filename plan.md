# Plan

## Missing inputs

- None.

## Scope assumptions

- Baseline is `origin/main` at `57dd2e30c441392997a5a3066de91fab3c522204`.
- The owner authorization in the current task supersedes older task-local prohibitions on branch, commit, push, PR, and merge actions.
- The existing global Codex instruction is the accepted Wave 2 activation mechanism.

## Affected files / areas

- `SPEC.md`, `plan.md`, and `tasks.md`.
- Inference policy/runtime boundary and focused semantic tests/schemas.
- Wave 2, PB4, tool-contract, registry, and generated release-gate documentation.

## Steps

1. Reconcile canonical specification, execution plan, task scope, and lifecycle evidence.
2. Add failing security tests for unverified and tunnel/proxy loopback listeners and explicit assurance metadata.
3. Implement the smallest fail-closed local Ollama listener/process verifier at the existing inference boundary.
4. Reconcile Wave 2 activation and PB4-03/PB4-04 registry states and update directly affected documentation/contracts.
5. Regenerate canonical release gates and run focused security, contract, fixture, schema, and documentation checks.
6. Run the relevant full regression through `ldw test parse`, build the evidence package, and review the complete diff.
7. Commit, push, open a PR, wait for required checks, merge under repository policy, and reverify merged `main`.

## Dependencies

- Step 2 depends on Step 1.
- Step 3 depends on the observed failing tests from Step 2.
- Step 4 depends on Steps 1 and 3.
- Step 5 depends on Steps 3 and 4.
- Step 6 depends on Step 5.
- Step 7 depends on acceptance of Step 6.

## Risks

- Local process inspection may be platform-specific; the production control must fail closed rather than downgrade silently.
- Generated governance documents may drift if registry changes are not regenerated with the repository script.

## Validation strategy

- Establish test outcomes only by piping captured runner output to `ldw test parse`.
- Run focused PB4/locality tests first, then schemas, fixtures, release-gate drift, compilation, secret scan where supported, full tests, and `git diff --check`.
- Re-run a bounded smoke after merge from synchronized `main`.

## Parallel work

- None; runtime, registry, generated documentation, and acceptance evidence are dependency-ordered.
