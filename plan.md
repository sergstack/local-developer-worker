# Plan

## Missing inputs

- None for deterministic Phase 1 construction. A real Ollama probe is optional evidence and cannot weaken deterministic gate results.

## Scope assumptions

- Gate/benchmark support code is allowed; production semantic clustering is not.
- The approved model fact (`qwen3:4b`) is source-reported and is not a reason to enable semantic policy.

## Affected files / areas

- `policy.toml`, Phase 1 planning documents, policy/gate source modules, schemas, sanitized fixtures, focused tests, validation scripts, and concise gate documentation.
- Existing Stage A report implementation and safety-matrix test file are protected from edits.

## Steps

1. Update execution artifacts and lock Phase 1 scope around the 10 required portfolio objects.
2. Implement `POLICY-01`: exact policy comment, deterministic endpoint parsing/resolution, fail-closed loopback guard, and no-I/O rejection evidence.
3. Build `REF-01` with at least 30 sanitized events plus grouping, separation, and exclusion ground truth; extend fixture validation.
4. Define `semantic_group` and Stage B portfolio schemas, then implement deterministic candidate validation, sanitized payload construction, fallback, and `needs_review` logic.
5. Add exact tests for `GATE-01` through `GATE-06` and `NR-01`; link POLICY-01 endpoint enforcement into `GATE-04` evidence.
6. Prove `GATE-07` by executing the unchanged Stage A safety matrix and comparing its source hash to the Phase 1 baseline.
7. Add the 10-object registry and runner that establishes pytest status through `ldw test parse`, continues across failures, and emits the required reconciled summary.
8. Validate schemas, fixtures, secret scan, deterministic reruns, full tests, policy diff, registry reconciliation, and Phase 1 acceptance.

## Dependencies

- Step 2 depends on Step 1.
- Step 3 depends on Step 2 by required execution order, although its data is otherwise independent.
- Steps 4–5 depend on REF-01 contracts from Step 3.
- Step 6 depends on the completed gate integration.
- Step 7 depends on exact evidence nodes from Steps 2–6.
- Step 8 depends on all prior steps.

## Risks

- DNS resolution must fail closed on empty, mixed, wildcard, or external results.
- Gate code must not perform classification or clustering; it only validates externally supplied candidates.
- Registry evidence must not mark objects complete from declarations alone.

## Validation strategy

- Capture pytest output with `-rA`, feed it to `ldw test parse`, and use its `run_status` as test evidence.
- Run schema, fixture, secret, compile, policy-diff, deterministic-output, and portfolio reconciliation checks.
- Keep a hash-based check that the Stage A safety-matrix source file is unchanged from `5a3d146`.

## Parallel work

- None. POLICY-01 then REF-01 is the required user order.
