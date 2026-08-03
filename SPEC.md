# SPEC

## Goal

Replace the static Stage A gate table with a self-verifying 20-item portfolio, record the user's advisory SA-16 choice, and complete the actionable v3 transition work without enabling Stage B.

## Current state

- `docs/release-gates.md` contains 16 hand-written gate rows whose test references can drift.
- The repository has privacy-filtered telemetry helpers but no append-only session journal or `ldw telemetry summary`.
- The SA-16 decision, Stage B entry document, and terminology audit are not represented as resumable portfolio items.

## Requirements

- Define 16 `gate` items (`SA-01` through `SA-16`) and four `action_item` items (`AI-01` through `AI-04`) in `docs/gate_registry.json`, validated by `schemas/portfolio_item.schema.json`.
- Generate `docs/release-gates.md` from the registry and verify byte-for-byte generation determinism.
- Add `ldw portfolio verify` and `ldw portfolio status`. Verification must collect and execute every declared gate test independently, continue after failures, reconcile classification, check action artifacts, preserve 20 inputs as 20 outputs, and persist resumable local state outside source control.
- Keep `AI-02` in `waiting_for_input` when `decision` is absent. When `decision.chosen_option` is explicitly recorded, verify it as a normal evidence-backed action item. Record option (a) through the exact AGENTS.md rule and `ldw doctor` reminder, and reject option (b); no session wrapper may be implemented.
- Add append-only, date-partitioned local CLI telemetry containing only `tool`, `input_bytes`, `output_bytes`, `latency_ms`, `status`, `fallback_used`, `context_reduction`, and `run_id`; add `ldw telemetry summary` with date filtering and v3 aggregates.
- Create `docs/stage-b-entry-gate.md` covering the first bounded semantic task, its evidence contract, and a pre-code regression gate while preserving all Stage A guarantees.
- Audit `PROJECT_DESCRIPTION.md` for market/team framing and change it only if a mismatch exists.

## Constraints

- Do not change `policy.toml`, enable `[semantic]`, implement an SA-16 enforcement option, or add/change/remove Git remotes.
- Do not run `git push`, `git fetch`, or `git pull` without a new explicit confirmation.
- Do not store code, logs, prompts, secrets, or provider responses in telemetry.
- Public behavior may change only by adding the three specified CLI commands and the documented local telemetry side effect.

## Acceptance criteria

- The registry contains exactly 20 unique objects in the required categories and ID ranges.
- Regenerating `docs/release-gates.md` produces byte-identical content.
- A fresh portfolio verification executes every gate evidence node and returns one status per object without stopping at the first failure.
- No item is `complete` without fresh executable or artifact evidence; removing `AI-02.decision` must restore `waiting_for_input`.
- AI-02 evidence must verify the new AGENTS.md rule and the actual `data.test_status_reminder` value returned by `ldw doctor`, not pre-existing advisory documentation.
- At least 10 real local CLI events produce a non-empty telemetry summary; append-only and safe-field tests pass.
- The Stage B entry document answers all three v3 questions and does not weaken Stage A.
- Local verification does not open Stage B; Stage A must first be merged and explicitly accepted.
- The full test suite, schema validation, fixture validation, secret scan, `ldw doctor`, portfolio commands, and telemetry summary pass.

## Risks

- Pytest parameterization can hide missing cases unless exact collected node IDs are stored and checked.
- Shared evidence tests must retain per-gate attribution.
- Date filtering must not add unsafe timestamp fields to telemetry events; journal files are partitioned by date instead.
- A source change after verification makes stored evidence stale and must not be reported as fresh.
