# SPEC

## Goal

Reconcile the accepted Local Developer Worker state with current governance and close the confirmed PB4 inference-locality control gap without expanding routing or architecture.

## Current state

- Wave 2 context and evidence contracts are implemented and accepted; the global Codex instructions already invoke them, but canonical Wave 2 records still say `accepted_not_activated` / `waiting_for_owner`.
- PB4-03 contract v2 is merged, tested, owner-selected, and supervised-active, while its registry field remains `qa_pending`.
- The production inference guard proves only a loopback transport endpoint. Repository evidence confirms that an SSH tunnel previously satisfied this check while inference ran on another host.
- Existing context pack, evidence build, facts-only reporting, and resumable-state primitives satisfy the current handoff/documentation contract.
- No accepted current architecture contract establishes repo-index candidate discovery as required current-scope functionality.

## Requirements

- Describe accepted Wave 2 root isolation, selection lineage, expansion, traceability, portability, context, evidence, and resumable-state behavior accurately.
- Record Wave 2 as globally active through the existing bounded Codex instruction while preserving all bypass and safety rules.
- Reconcile PB4-03 to the existing completed lifecycle status supported by merged implementation, acceptance evidence, and supervised activation.
- Before production Ollama transport, verify that the loopback listener is an observable local Ollama process; reject unverified, tunnel, proxy, and ambiguous listeners.
- Report assurance precisely: local endpoint/process/runtime verification is observable, while physical inference locality remains unprovable from available signals.
- Preserve explicit-manual semantic routing, deterministic fallback, disabled code artifacts, and existing v1/v2 contracts.
- Update focused tests, security evidence, registry output, and directly affected documentation.

## Constraints

- No external provider calls, model pulls, production deployment, secret access, migration, new dependency, public schema break, automatic semantic routing, or unrelated refactor.
- Do not claim cryptographic or physical-host attestation.
- Do not implement repo-index orchestration or standalone handoff/documentation services without an accepted current-scope contract.
- Test outcomes must be established through `ldw test parse`.
- Changes must remain reversible with a normal Git revert; activation rollback is removal of the bounded global instruction and restoration of the prior Wave 2 registry state.

## Acceptance criteria

- Canonical Wave 2 and PB4-03 statuses match observed accepted/active behavior.
- Current Wave 2 behavior is documented without stale pre-implementation claims.
- A synthetic SSH/tunnel or proxy listener is rejected before transport.
- A verified local Ollama listener is accepted and returns explicit bounded assurance metadata.
- Unavailable or ambiguous process verification is policy-blocking and does not call transport.
- Existing non-loopback, fallback, deterministic accounting, schema, fixture, generated-document, and relevant regression checks pass.
- Repo-index and handoff/documentation classifications are recorded without speculative implementation.
- Diff review, commit, push, PR checks, merge, and post-merge verification complete when repository governance permits.

## Risks

- Process-name/executable verification is stronger than loopback-only validation but is not cryptographic service attestation and cannot prove where every inference computation occurs.
- Listener inspection depends on local operating-system process tools; absence or ambiguity must fail closed for semantic inference.
- Status reconciliation may expose older historical documents that remain intentionally historical rather than canonical.
