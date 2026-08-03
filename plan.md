# Plan

## Missing inputs

- None. `codex-autonomous-brief-v4.md` and its referenced v3 brief are available as the external task package.

## Scope assumptions

- Portfolio run state is generated local data under `.repo_index/`; the canonical definitions remain in `docs/gate_registry.json`.
- Date filtering uses date-partitioned JSONL files so telemetry events remain restricted to the eight approved fields.

## Affected files / areas

- Portfolio schema, registry, generator, runtime verifier, CLI dispatch, telemetry/session logging, Stage B documentation, and focused tests.

## Steps

1. Encode all 20 portfolio objects with exact pytest node IDs and artifact checks; add schema validation.
2. Add deterministic Markdown rendering and replace the hand-written gate document with generated output.
3. Add append-only safe telemetry and `ldw telemetry summary`.
4. Add non-blocking `ldw portfolio verify` and resumable `ldw portfolio status`.
5. Record the user's advisory AI-02 decision with artifact evidence and a decisionless fallback test; complete AI-03 documentation and AI-04 terminology audit.
6. Add focused contract, integration, security, drift, and invariant tests.
7. Record at least 10 real CLI events, run fresh reconciliation, then execute the full acceptance suite.

## Dependencies

- Step 2 depends on Step 1.
- Step 4 depends on Steps 1 and 2.
- Step 7 depends on all implementation and test steps.

## Risks

- Exact parameterized pytest node IDs may change and must surface as reconciliation defects.
- Telemetry or portfolio state writes must never alter CLI evidence output or source-controlled files.

## Validation strategy

- Targeted unit/integration/security tests after each component, followed by the complete suite and every command in the v4/v3 acceptance lists.

## Parallel work

- Gate-node mapping and action-item artifact analysis may run independently before implementation; root integrates and re-verifies all results.
