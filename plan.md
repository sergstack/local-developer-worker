# Plan

## Missing inputs

- None.

## Scope assumptions

- Current baseline is `8ec8d004a039472ae41d627b78f545b73083d142`.
- CLI production exposure is not observed; the confirmed defect is an enforcement-contract gap on the injected-transport Python/internal surface.

## Affected files / areas

- `SPEC.md`, `plan.md`, and `tasks.md`.
- `src/local_developer_worker/stage_b_cluster.py`.
- Deterministic Stage B test process evidence and focused regression tests.
- PB4-04 defect evidence in the canonical registry and directly affected tool-contract text.

## Steps

1. Add a regression proving an injected transport is reachable when runtime verification is unavailable on the pre-fix implementation.
2. Add repository-native synthetic local Ollama listener/process evidence for deterministic Stage B tests.
3. Remove the custom-transport verifier bypass from `log_cluster` without exposing a replacement bypass.
4. Record the corrective defect and update the directly affected contract wording.
5. Run focused PB4-04, Stage B, PB4, and full regression checks through `ldw test parse`, plus deterministic validators.
6. Build requirements traceability and complete security, diff, and acceptance judges.
7. Commit, push, create/reuse a PR, merge when gates permit, and verify merged `main`.

## Dependencies

- Step 2 depends on the failing evidence from Step 1.
- Step 3 depends on Steps 1–2.
- Step 4 depends on Step 3.
- Steps 5–6 depend on Steps 3–4.
- Step 7 depends on acceptance of Step 6.

## Risks

- A broad test fixture could mask the security boundary unless regression tests explicitly replace the observed listener with an unverified one.

## Validation strategy

- Use `pytest -q -rA` captured through `ldw test parse` for every claimed test result.
- Run focused locality and production-path tests, affected PB4 regression, full suite, schemas, fixtures, release-gate drift, secret scan, compilation, and `git diff --check`.

## Parallel work

- None; the reproduction, correction, and security judge are dependency-ordered.
