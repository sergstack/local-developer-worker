# Wave 2 acceptance report

Status: `complete`
Overall state: `accepted_and_activated`
Global activation: `active`

## Accepted services

- `ldw context pack`: accepted for bounded, traceable selection and linked expansion inside an explicitly allowed repository root.
- `ldw evidence build`: accepted for lineage-preserving evidence and resumable bounded task state inside an explicitly allowed repository root.

The enclosing `ToolResult` remains version `1.0.0`; both payload contracts are version `2.0.0`. Legacy payload keys remain readable.

## Frozen evaluator evidence

The evaluator used 15 sanitized cases, including 11 cases eligible for reduction measurement. Two byte-identical runs produced exact stdout SHA-256 `9e03a4932404230cae14949d41aea97bf4740f988bf829d72b7339bcf3cf0564`.

context-reduction figures used a synthetic inventory with manually assigned sizes; not measured on real files, not a promotion criterion

Observed metrics:

- critical file omissions: `0`;
- sensitive file leaks: `0`;
- outside-root reads: `0`;
- silent exclusions: `0`;
- included traceability: `1.0`;
- excluded visibility: `1.0`;
- evidence lineage completion: `1.0`;
- deterministic case rate: `1.0`;
- safe expansion, sensitive blocking, outside-root blocking, previous-package linkage, and resume rates: `1.0`;
- median eligible context reduction: `0.9072`;
- eligible cases with at least 25% reduction: `1.0`.

The frozen corpus SHA-256 is `c37bc8fc306c9b31b69544a607b451217a8a3e602676fd128dd92b36f07b57b3`.

`raw_repository_reread_rate` and `time_to_actionable_context` are `NOT MEASURED`; no claim is made for either metric.

## Portability evidence

Read-only smoke checks passed on three real repositories: this Python package, `audi_contrpatrty`, and the Hermes parsing repository. Each run found its bounded critical file, blocked the synthetic sensitive and outside-root requests, completed source lineage, and left the repository status byte-identical before and after. Exact smoke stdout SHA-256: `c3540ac43de3cefa14d9cc720084c55b225f96c7e55324b9c96455ee5989ff6e`.

The installed global command is callable at `/Users/sst/.local/bin/ldw` and exposes the accepted context-packer capability. The global Codex instructions require `ldw context pack` for non-trivial multi-file or unfamiliar-repository work and `ldw evidence build` before resumable/final reporting. This existing bounded instruction is the active Wave 2 integration; it does not authorize automatic repository-wide reading, sensitive-file inclusion, edits, commits, or merges.

## Verification

- Full suite: 158 observed tests passed, established via `ldw test parse`.
- 15 JSON schemas, 20 Stage A items, 10 Stage B Phase 1 items, and 8 Stage B Phase 2 items validated.
- Benchmark manifest, 34 Stage B reference events, and 15 frozen Wave 2 cases validated.
- Secret scan, compilation, generated release-gate check, and `git diff --check` passed.

## Known limitation

The current policy root check reliably isolates a single allowed root, as used independently for every portability case. A policy containing multiple roots effectively evaluates only its first entry when that entry does not contain the requested path. This does not bypass root isolation, but multi-root policy portability remains a separate security-sensitive change and was not modified in this scope.

## Active integration and rollback

The accepted instruction is represented in `docs/wave-2-codex-integration.patch.md` and is active through the equivalent global Codex rule. This reconciliation did not mutate global installation, configuration, AGENTS files, external repositories, or deployment state.

To roll back usage, stop sending `mode=expand` and consume the retained legacy fields. A code rollback may restore the previous context/evidence implementation without changing Stage B, global configuration, or external repositories.
