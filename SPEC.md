# SPEC

## Goal

Ensure transport dependency injection cannot disable PB4-04 runtime-locality enforcement.

## Current state

- Baseline `origin/main` is `8ec8d004a039472ae41d627b78f545b73083d142`, the merge of PR #10; there are no intervening commits.
- `log_cluster` runs the canonical locality verifier for its normal Ollama transport but explicitly passes `runtime_verifier=None` when a custom transport is injected.
- CLI `log cluster` and `log process` do not expose transport injection; production exploitability is not observed.
- Internal PB4 evaluation and Python/test call sites can inject transport, so the enforcement-contract bypass is confirmed independently of production exposure.

## Requirements

- Transport selection must not select or disable security policy.
- Every `log_cluster` transport, including an injected transport, must run only after canonical endpoint and runtime verification succeeds.
- Unverified, absent, ambiguous, SSH, socat, or proxy listeners must be policy-blocking and must not reach transport.
- A verified local Ollama listener must permit one deterministic injected-transport call in tests.
- Production-facing semantic execution must expose no verifier-disable or allow-all-verifier argument.
- Preserve bounded assurance metadata, including `physical_inference_locality: not_provable`.
- Preserve routing, model selection, schemas, fallback behavior, and all unrelated architecture.

## Constraints

- No provider/model calls, new dependency, schema change, public verifier injection argument, automatic-routing change, or unrelated refactor.
- Lower-level `guarded_inference_call` may retain its explicit deterministic test seam; `log_cluster` must always use its canonical default.
- Test status must be established through `ldw test parse`.
- Git delivery is authorized only through `codex/pb4-04-transport-verifier-enforcement`, never direct to `main`.

## Acceptance criteria

- The pre-fix implementation reproduces custom transport reachability when runtime verification is unavailable.
- After correction, the same case returns `policy_blocked` and transport calls remain zero.
- Verified synthetic local Ollama process evidence permits exactly one custom deterministic transport call.
- Existing PB4-04 tunnel/proxy/unverified tests and relevant Stage B/full regressions pass.
- Security and diff judges pass with no production verification bypass, schema change, or scope creep.
- Commit, push, PR, merge, and post-merge verification complete under repository policy.

## Risks

- Deterministic tests need synthetic OS listener/process evidence; the fixture must exercise, not bypass, the canonical verifier.
- Process identity remains non-cryptographic and cannot prove physical inference locality.
