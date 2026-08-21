# Adaptive Codex Routing tasks

- [x] Record Goal Mode handoff to Codex and create `codex/adaptive-codex-routing`.
- [x] Preserve existing root delivery documents and create a namespaced specification.
- [x] Pass implementation guard against this specification, plan, scope, checks, and rollback.
- [x] Implement validated Codex policy, signal catalog, routing, alias resolution, and fixed-profile mode.
- [x] Implement capability preflight, isolated run/resume, bounded JSONL parsing, fallback, escalation, and verification.
- [x] Integrate CLI, public result contract, schemas, telemetry event, and summary aggregates.
- [x] Add routing-class, configuration, runner, escalation, fallback, privacy, security, schema, and CLI regression tests.
- [x] Update README and policy example.
- [x] Run focused tests and parse observed results with `ldw test parse`.
- [x] Run the canonical LDW suite and parse observed results with `ldw test parse`.
- [x] Run schema fixtures and `git diff --check`.
- [x] Complete pipeline-readiness and acceptance reviews; build LDW Git/evidence handoff.

## Scope lock

Allowed: `src/local_developer_worker/cli.py`, `policy.py`, `telemetry.py`, `session_log.py`; new Codex routing/runner modules; versioned schemas; focused tests; `policy.toml`; README and telemetry/Codex documentation; this namespaced delivery directory.

Forbidden: Stage B semantic contracts; unrelated refactors; secrets; provider credentials; real provider calls in tests; automatic commits, merges, deployments, resets, stashes, worktree changes, or network enablement.

Public behavior may change only by adding the opt-in `ldw codex run` surface and Codex telemetry records. Existing commands, safety defaults, ToolResult contract, and disabled behavior remain compatible.

Validation: fake-runner unit/integration tests, schema validation, security/privacy assertions, existing suite, LDW-parsed test evidence, and `git diff --check`.

Rollback: `[codex].enabled = false` disables the adapter; `[codex].adaptive_routing = false` retains execution with the configured fixed profile.
