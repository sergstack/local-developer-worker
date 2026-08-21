# Adaptive Codex Routing implementation plan

1. Freeze the v4 contract and bounded scope in this directory, preserving the repository's existing delivery documents.
2. Add policy parsing and deterministic routing with alias/escalation validation independent of provider model names.
3. Add a fail-closed Codex capability adapter, isolated process execution, JSONL observation, exact-session resume, verification, and public result projection.
4. Integrate `ldw codex run`, dedicated privacy-safe telemetry, schemas, and fixed-profile rollback behavior without changing existing command contracts.
5. Add unit, integration, contract, security, escalation, fallback, and regression tests using injected fake runners only.
6. Update user documentation and example policy.
7. Run focused and full checks, parse test evidence through LDW, run `git diff --check`, perform production-readiness review, and complete acceptance evidence.

Dependencies: steps 2–4 depend on the frozen contracts; tests follow their corresponding implementation and precede documentation/acceptance. Rollback is configuration-only through `codex.enabled` and `codex.adaptive_routing`.
