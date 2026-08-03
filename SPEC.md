# SPEC

## Goal

Accept Wave 2 as a portable, deterministic Context Packer and Evidence Package layer for bounded use across local repositories.

## Current state

- `ldw context pack` and `ldw evidence build` exist in canonical commit `1e738256dfbd72fcac4386d8a3c9a0d776f3e6d9`.
- Context selection accepts caller-supplied file metadata and deterministic signals, but does not require a repository root, expose full selection lineage, or implement expansion.
- Evidence packages preserve legacy observed inputs and a content hash, but do not provide complete per-item lineage or a resumable state contract.
- Context and evidence schemas validate only minimal required keys.
- Cross-repository portability and the required reduction thresholds are not yet established.

## Requirements

- Require an explicit, allowed repository root and block lexical, resolved-path, and symlink escapes.
- Preserve sensitive, binary, ignored, generated, budget, unsupported, and unselected exclusions visibly.
- Give every included file a selection reason, evidence source, and relevance status without promoting candidates to observed facts.
- Support deterministic bounded expansion linked to a previous context package and reapply all safety checks.
- Build evidence only from supplied observed, deterministic-derived, model-derived-candidate, user-provided, or unknown items with applicable lineage.
- Preserve visible missing evidence, open questions, constraints, next bounded action, and resumable task state.
- Freeze at least 15 sanitized reference cases and evaluate critical omissions, traceability, exclusions, safety, expansion, determinism, and context reduction.
- Run read-only smoke checks in at least three real repositories without changing them.
- Record global CLI source provenance and prepare, but do not apply, the owner-gated global Codex integration text.
- Synchronize public schemas, migration notes, documentation, and the canonical governance registry.

## Constraints

- Do not use network access, semantic indexing, embeddings, model inference for facts, automatic routing, source edits, or mutating Git operations.
- Do not read or emit sensitive contents, provider responses, neighboring repositories, or an entire repository as an implicit fallback.
- Do not change global configuration, global `AGENTS.md`, or the global `ldw` installation.
- Keep legacy input and output fields readable where downstream consumers already use them; add an explicit Wave 2 contract version for new fields.
- Test status must be established through `ldw test parse`.
- Do not stage, commit, push, create or update a PR, merge, or deploy without separate approval.

## Acceptance criteria

- Frozen corpus has at least 15 cases and cannot rewrite expected critical files from evaluator output.
- Critical omissions, sensitive inclusions, outside-root reads, symlink escapes, and silent exclusions are all zero.
- Included traceability and excluded visibility are both 100%.
- Eligible multi-file cases have median context reduction of at least 40%, and at least 80% reduce context by at least 25%.
- Allowed expansion, sensitive blocking, outside-root blocking, and previous-package linkage are each 100% on the acceptance set.
- Evidence lineage is complete for accepted packages; missing tests remain `NOT RUN`, `incomplete`, or `unknown`; no root cause is asserted.
- Resume and handoff checks recover objective, observed state, considered files, tests, failures, constraints, missing evidence, and next bounded action.
- Three real repositories pass read-only portability smoke.
- Global CLI works outside the Worker repository, with accepted-source activation reported honestly as active or pending.
- Schemas, fixtures, release-gate generation, secret scan, compilation, full tests, evaluator, and deterministic reruns pass.

## Risks

- Adding lineage and expansion can break downstream consumers unless legacy fields remain available.
- Caller-supplied inventories can contain misleading or unsafe paths; every path needs deterministic validation.
- Reduction metrics can be misleading on already-minimal inputs; such cases must be visibly bypassed.
- The globally installed editable CLI may point to a different or unaudited worktree, so global activation may remain pending after repository acceptance.
