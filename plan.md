# Plan

## Scope

Implement PB2-01 through PB2-08 on `codex/stage-b-phase-2-log-clustering`, based on merge commit `a8e0484`.

## Steps

1. Record approved SA-14 option (b) and exact evidence without SA-17.
2. Add default-off policy capability plus qwen3:4b and loopback 11435 configuration; remove probe literals.
3. Add production CLI dispatch using the existing Phase 1 sanitizer, loopback guard, validator, and fallback.
4. Integrate optional model-derived candidates into reports while freezing the legacy byte output.
5. Synchronize public-command coverage, schemas, governed feature metadata, and documentation.
6. Re-run Stage A and Phase 1 portfolios; preserve the legacy safety matrix through an exact authorized-delta check.
7. Run one supervised REF-01 call against the real model and record only privacy-safe evidence.
8. Add rollback documentation, the eight-item Phase 2 registry/runner, and final acceptance validation.

## Validation

- Establish pytest outcomes only through `ldw test parse`.
- Run compileall, schema validation, fixture validation, secret scan, full tests, all three portfolios, deterministic reruns where applicable, release-gate drift check, and `git diff --check`.
- Treat any raw model response persistence, non-loopback call, mutation capability, Stage A regression, or false live-run claim as a hard blocker.
