# Tasks

## Phase 2 implementation

- [x] Create `codex/stage-b-phase-2-log-clustering` from merged Phase 1 commit `a8e0484`.
- [x] PB2-01: apply owner-approved SA-14 option (b), preserve default-deny assertions, and add exact wording evidence.
- [x] PB2-02: configure default-off semantic clustering, qwen3:4b, and 127.0.0.1:11435 only in policy.
- [x] PB2-03: add guarded `ldw log cluster` production dispatch and privacy-safe fallback tests.
- [x] PB2-04: add separate report semantic candidates with a byte-identical legacy regression test.
- [x] PB2-05: synchronize SA-01, schemas, governed feature metadata, README, and contracts without SA-17.
- [x] PB2-06: restore and observe Stage A 20/20 and Phase 1 10/10 after the exact authorized matrix delta.
- [x] PB2-07: observe a real qwen3:4b response on 11435 and record only sanitized summary evidence.
- [x] PB2-08: document rollback and historical evidence behavior.
- [x] Add the exact eight-object Phase 2 registry and deterministic portfolio runner.

## Remaining validation

- [x] Run focused Phase 2 portfolio.
- [x] Run full pytest and establish status through `ldw test parse`.
- [x] Run compile, schemas, fixtures, secret scan, release-gate drift, all three portfolios, and diff checks.
- [x] Complete independent review and acceptance-check against SPEC.

## Forbidden actions

- Do not enable default semantic policy or code_artifact.
- Do not grant edit, commit, merge, deploy, or external-network capabilities.
- Do not store raw model responses, prompts, raw logs, or secrets.
- Do not push, open a PR, or merge without separate authorization.
