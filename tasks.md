# Tasks

## Preparation

- [x] Read the v4 brief, referenced v3 requirements, repository instructions, and current implementation.
- [x] Audit current gate evidence names against pytest collection.

## Scope lock

- Allowed files: `SPEC.md`, `plan.md`, `tasks.md`, `.gitignore` only if needed for generated state, portfolio/telemetry source and scripts, schemas, generated/relevant docs, and focused tests.
- Forbidden files: `policy.toml`, the ignored DOCX, unrelated benchmarks and fixtures.
- Allowed actions: local reads/writes, local branch creation, pytest and validation commands, generated local state under `.repo_index/`.
- Forbidden actions: push/fetch/pull, remote mutation, Stage B enablement/runtime, SA-16 option implementation, secret/raw-content telemetry.
- Public behavior may change only through `ldw telemetry summary`, `ldw portfolio verify`, `ldw portfolio status`, and documented local telemetry recording.

## Implementation

- [x] Add and validate the 20-object canonical registry.
- [x] Add deterministic release-gate Markdown generation.
- [x] Add append-only safe session logging and telemetry summary.
- [x] Add non-blocking portfolio verification and resumable status.
- [x] Add the Stage B entry-gate document.
- [x] Record the terminology audit outcome without changing `PROJECT_DESCRIPTION.md` unless required.
- [x] Record AI-02 option (a), reject option (b), and preserve waiting-for-input behavior when `decision` is absent.
- [x] Add the exact test-status rule to AGENTS.md and expose the same reminder in `ldw doctor`.

## Validation

- [x] Add tests for registry cardinality, IDs, schema, exact node IDs, generated-doc drift, and 20-in/20-out behavior.
- [x] Add tests for non-blocking defects, advisory classification, action artifacts, the recorded AI-02 decision, and the decisionless fallback state.
- [x] Require AI-02 artifact evidence from the new AGENTS.md rule and actual doctor output rather than pre-existing documentation.
- [x] Add tests for telemetry append-only behavior, exact safe fields, summaries, and date filtering.
- [x] Run targeted checks, then full pytest, schema/fixture validation, secret scan, doctor, telemetry summary, portfolio verify/status, and diff checks.

## Acceptance mapping

- Registry/generator tasks prove the canonical-source and byte-identical Markdown criteria.
- Portfolio tests and a fresh run prove isolated execution, non-blocking reconciliation, 20 outputs, and evidence-backed completion.
- Telemetry tests plus 10+ real local events prove AI-01.
- The decision table, artifact check, and decisionless regression prove AI-02 without weakening the user-choice guard.
- The Stage B document and terminology check prove AI-03 and AI-04.

## Forbidden actions

- Do not modify `policy.toml` or enable semantic functionality.
- Do not implement any SA-16 enforcement option.
- Do not add, remove, or change remotes.
- Do not push, fetch, or pull without a new explicit confirmation.

## Documentation

- [x] Regenerate `docs/release-gates.md` from the registry.
- [x] Update telemetry/tool-contract documentation and create `docs/stage-b-entry-gate.md`.
