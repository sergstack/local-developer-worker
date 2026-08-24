# Adaptive Codex Routing

## Goal

Add an opt-in Codex execution adapter to Local Developer Worker (LDW). The adapter deterministically classifies an authorized task, resolves a policy-defined model alias and reasoning effort, launches Codex with explicit isolation controls, verifies the result, and either passes, resumes the exact session with a stronger profile, or blocks.

## Current state

LDW is a deterministic, read-only evidence CLI. Its opt-in, policy-gated `ldw codex run` adapter launches an isolated advisory child only after its routing, authority, and executable checks pass. Existing repository-root, telemetry, and ToolResult boundaries remain compatible.

## Requirements

1. Register `ldw codex run`; accept exactly one JSON object on stdin. Required inputs are `task` and `repository_root`. Optional inputs are `policy_path`, `task_class`, `profile`, and a bounded `verification` object.
2. Keep execution disabled unless both `[codex].enabled = true` and the requested task is explicitly authorized by the command invocation. `[codex].adaptive_routing = false` restores the fixed `[codex].default_profile` path.
3. Route only to abstract profiles `efficient`, `balanced`, or `frontier`. Concrete models and supported effort values live exclusively in `[codex.aliases.*]`; classifier code must contain no provider model identifier.
4. Use this deterministic precedence: policy risk floor; permitted explicit profile override; structured `task_class`; ordered high-risk signals; ordered bounded-change signals; ordered routine signals; otherwise `balanced` with uncertainty. Higher-risk matches win. An override may not lower the risk floor unless policy explicitly permits downgrades.
5. Validate the complete Codex policy before execution: flags, default and maximum profiles, alias graph, effort values, fallback references, escalation graph, executable allowlist, limits, and verification allowlist. Reject cycles, missing aliases, and unsupported efforts.
6. Resolve the Codex executable to an absolute, executable, non-symlinked path included in policy. Perform a bounded version/capability preflight and fail closed for unsupported invocation families.
7. Launch without a shell. Pass the task through stdin, use JSONL output, set the working directory to the authorized repository root, ignore user configuration, and explicitly set model, reasoning effort, sandbox, approval policy, and execution limits.
8. Preserve the existing repository/root/security boundaries. A write-capable sandbox requires `[codex].allow_write = true`; the adapter never commits, merges, deploys, or performs mutating Git administration. A dirty worktree is allowed and must be preserved; baseline and post-run Git facts are verification evidence, never a reset target. An explicitly allowed non-Git directory is permitted only for `allow_write = false`, `sandbox = "read-only"`, and `verification.kind = "execution"`; it must emit visible `git_evidence_not_available` evidence. Command/test verification and any write-capable path still require Git facts.
9. Parse provider JSONL in memory into a versioned capability contract. Derive only terminal state, stable error code, token counts, mutation observation, and exact thread identifier. Provider responses, prompts, source, commands, paths, concrete model identifiers, and thread identifiers must not enter LDW telemetry or persistent LDW logs.
10. Verification has an explicit source contract. With `allow_write = false` and `sandbox = "read-only"`, `execution` is permitted for every route and passes only on provider completion; it is advisory execution metadata, not semantic-quality acceptance. A mutation-capable task under a write-capable policy requires `command` or `test` verification. Both use an argv array that exactly matches a policy allowlist, direct process launch, configured absolute executable allowlist, repository cwd, bounded output, and timeout. `test` status must be derived through the existing test parser with `command_observed=true` and the observed exit code.
11. A pass requires both provider completion and verification `passed`. Successful execution never escalates.
12. Fallback to another alias is permitted only for a stable `model_unavailable` provider code and only before any mutation is observed. Fallback does not increase the escalation counter.
13. Escalation requires explicit failed/uncertain verification or a configured retriable execution error, an observed exact thread identifier, remaining configured budget, and a higher profile in the escalation graph. Resume the exact identifier; never use `--last` and never start a fresh blind retry. Reassert model, effort, cwd, sandbox, approval, ignored user config, and limits on every resume.
14. The maximum escalation count is configurable and bounded. Missing thread identity, exhausted budget, unavailable route, failed preflight, or unsafe verifier produces a terminal blocked/failed result without retry.
15. Public ToolResult data must expose only abstract route facts (`profile`, `model_alias`, `effort`, controlled signal code, confidence, deterministic risk floor, and policy revision hash), terminal status, verification status, fallback count, escalation count, and nullable token counts. `pass` maps to ToolResult `success` and CLI exit 0; every other terminal Codex outcome maps to a non-success ToolResult and CLI exit 2.
16. Add versioned privacy-safe Codex telemetry. Legacy `codex_run_event_v1` remains readable; new `codex_run_event_v2` and routing calibration `2.4.0` records add a random `execution_id` to distinguish actual invocations. `run_id` remains the deterministic ToolResult input fingerprint. The exact allowlist otherwise contains only routing/status counters and nullable token fields; no prompt, path, response, or thread identifier is retained. Credits are intentionally excluded because Codex JSONL has no stable credit field.
17. Existing generic telemetry remains backward compatible. Telemetry summary exposes aggregate Codex run counts, profile/status counts, escalation/fallback totals, and token totals without sensitive content.
18. Publish versioned JSON schemas for Codex input, public result data, and telemetry. Validate representative fixtures in tests.

## Constraints

- No network-dependent test and no real provider invocation in the automated suite.
- No automatic commit, merge, deployment, worktree creation, checkout, reset, stash, or cleanup.
- No prompt/source/provider payload persistence in LDW-owned storage.
- No Stage B semantic-routing contract changes.
- Implementation scope is limited to CLI/policy integration, new routing/runner modules, versioned schemas, focused tests, policy example, and relevant documentation.
- Existing canonical LDW tests and public ToolResult schema remain valid.

## Acceptance criteria

1. With the feature enabled, `ldw codex run` deterministically selects a profile and effort for every routing class.
2. The selected alias model and effort are present in the actual fake-runner argv/config evidence.
3. A verified failure can resume the exact session at most the configured number of times.
4. Successful verified execution has zero escalations.
5. Changing alias model values requires no classifier modification.
6. Disabled adaptive routing uses the configured fixed profile.
7. Disabled Codex execution, disallowed roots, write-policy violations, invalid executable identity, invalid configuration, and unsafe verifiers fail closed.
8. Selected-model unavailability follows configured fallback and fails safely when fallback is impossible.
9. Dirty worktrees are preserved and no mutating Git command is issued.
10. Telemetry contains only the exact v1 allowlist and aggregates profiles, statuses, escalations, fallbacks, and tokens.
11. CLI regression, routing, escalation, policy validation, schema fixtures, security tests, and the existing LDW suite pass.
12. Test outcomes are established through `ldw test parse`; `git diff --check` passes.
13. Setting `[codex].enabled = false` prevents execution; setting `[codex].adaptive_routing = false` restores the fixed profile.

## Risks

- Provider JSONL or CLI flags can change; capability preflight and a versioned parser must fail closed.
- Exact-session resume depends on an observed provider thread ID; absent identity blocks escalation.
- Model-unavailable errors may be inconsistent across provider versions; only stable mapped codes permit fallback.
- Write-capable Codex execution has a wider authority surface; it remains separately policy-gated and verification-bound.
- Provider token accounting may be absent; telemetry must preserve `null` rather than infer values.
