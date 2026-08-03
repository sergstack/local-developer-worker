# Tasks

## Preparation

- [x] Create `codex/wave-2-acceptance-portability` in `/Users/sst/prod/local-developer-worker-wave2` from canonical `origin/main`.
- [x] Confirm `ldw context pack` and `ldw evidence build` exist in canonical history.
- [x] Inspect current implementations, schemas, tests, policy boundaries, and documentation.
- [x] Record the W2-00 baseline document before implementation.
- [x] Freeze the 15-case Wave 2 reference corpus.

## Scope lock

- Allowed files: `SPEC.md`, `plan.md`, `tasks.md`, `README.md`, `benchmarks/task_manifest.json` for required size synchronization, `src/local_developer_worker/{cli.py,tools.py,contracts.py,portfolio.py,stage_b_portfolio.py}` where the last file only preserves the existing Stage B safety-matrix assertion after the new explicit-root contract, `schemas/{context_package.schema.json,evidence_package.schema.json}`, `fixtures/wave2/**`, `scripts/{run_wave2_evaluator.py,run_wave2_portability_smoke.py,validate_schemas.py,validate_fixtures.py,generate_release_gates.py}`, `tests/wave2/**`, directly affected existing context/evidence contract and registry tests, `docs/{wave-2-baseline.md,wave-2-migration.md,wave-2-acceptance.md,wave-2-codex-integration.patch.md,tool-contracts.md,gate_registry.json,release-gates.md,telemetry.md}`.
- Forbidden files: global `~/.config/local-developer-worker/**`, global `~/.codex/AGENTS.md`, global tool installation, Stage B runtime/gate/model files, `policy.toml`, external repository files, and unrelated project files.
- Allowed actions: inspect, bounded local edits, sanitized fixtures, local tests, deterministic evaluators, read-only external-repository smoke, and owner-package preparation.
- Forbidden actions: `git add`, commit, push, PR creation/update, merge, deploy, global activation, external repository edits, semantic indexing, embeddings, model-derived facts, automatic routing, and mutating Git commands.
- Public behavior rule: context and evidence contracts may add versioned Wave 2 fields and validation required by `SPEC.md`; existing legacy fields must remain readable and must not silently change meaning.

## Implementation

- [x] Add explicit allowed-root and safe relative-path validation for context and evidence commands.
- [x] Add traceable included and excluded records with controlled reason and relevance values.
- [x] Add visible low-benefit and unsupported selection outcomes plus deterministic byte metrics.
- [x] Implement bounded expansion with previous-package linkage and repeated safety checks.
- [x] Add validated evidence items with complete applicable lineage and origin classification.
- [x] Add resumable objective, observed state, considered files, tests, failures, constraints, missing evidence, and next-action state.
- [x] Preserve legacy context and evidence input/output keys.
- [x] Add privacy-safe evaluator metrics without expanding production telemetry safe fields.

## Validation

- [x] Add focused context selection, expansion, evidence lineage, safety, determinism, resume, and unsupported-project tests.
- [x] Validate the 15-case frozen corpus and immutable expected critical files.
- [x] Verify zero critical omissions, sensitive inclusions, outside-root reads, symlink escapes, and silent exclusions.
- [x] Verify 100% included traceability, excluded visibility, expansion policy reapplication, and lineage completion.
- [x] Verify reduction thresholds using Python-calculated eligible-case metrics.
- [x] Run three real-repository read-only smoke checks and compare pre/post repository state.
- [x] Verify global CLI source provenance and outside-repository command availability without reinstalling it.
- [x] Run focused and full pytest through `ldw test parse` plus all required deterministic checks.

## Acceptance mapping

- Context safety and traceability: implementation tasks 1–3 and validation tasks 1–4.
- Expansion: implementation task 4 and validation tasks 1, 3, and 4.
- Evidence lineage and resume: implementation tasks 5–6 and validation tasks 1 and 4.
- Context economics: implementation task 8 and validation task 5.
- Portability and activation truthfulness: validation tasks 6–7.
- Overall acceptance: all validation tasks plus governance and documentation tasks.

## Forbidden actions

- Do not stage, commit, push, create/update a PR, merge, or deploy.
- Do not modify global configuration, global AGENTS, or the global `ldw` installation.
- Do not modify external repositories or read sensitive file contents.
- Do not claim acceptance from CLI presence or local tests alone.
- Do not turn candidate relevance, open questions, semantic groups, or hypotheses into observed facts.

## Documentation

- [x] Document Wave 2 contract versioning and migration compatibility.
- [x] Update README and tool contracts with bounded selection, expansion, evidence lineage, and bypass behavior.
- [x] Synchronize the canonical registry and generated release gates.
- [x] Prepare, but do not apply, the exact owner-gated global Codex integration patch.
- [x] Produce the observed Wave 2 acceptance report and rollback instructions.
