# Local Developer Worker

`ldw` produces deterministic, evidence-linked JSON for logs, tests, Git state, file inventory, context selection, and factual reports. It is a local CLI for Codex workflows, not an autonomous coding agent.

## Install and run

```bash
uv sync --extra dev
uv run ldw doctor
printf '%s' '{"text":"ERROR failed"}' | uv run ldw log parse
```

All commands accept one JSON object on stdin and write one versioned JSON envelope to stdout. Diagnostics are written to stderr. The default policy blocks network access, edits, commits, merges, deployments, and semantic-model capabilities. Bounded log clustering remains default-off and requires both `[semantic].enabled` and `[automatic].semantic_log_clustering`; `code_artifact` is never enabled.

## Portfolio and personal telemetry

```bash
uv run ldw portfolio verify
uv run ldw portfolio status
uv run ldw portfolio verify --only AI-01
uv run ldw telemetry summary --from-date 2026-08-01 --to-date 2026-08-31
```

The 20-item Stage A portfolio is defined in `docs/gate_registry.json`; `docs/release-gates.md` is generated from it. Verification runs each declared gate test independently, checks transition artifacts, and saves resumable local state under `.repo_index/`. CLI calls append privacy-safe events to date-partitioned local JSONL files; source text, logs, prompts, secrets, and provider responses are never recorded.

Stage B Phase 1 remains a validation workflow. Run its separate 10-object regression portfolio with `PYTHONPATH=src python scripts/run_stage_b_portfolio.py`; see `docs/stage-b-phase-1.md`.

`ldw log cluster` accepts only parsed Stage A log events under `events`. When narrowly enabled, it reads the model and loopback endpoint from `policy.toml`, validates model candidates through the Stage B gate, and returns normalized `model-derived` groups or an explicit observed-event fallback. Raw model responses are not emitted or recorded.

## Safety

Repository tools require an explicit `repository_root`. The inventory blocks secret-like paths and symlinks escaping that root. Git collection is read-only. Unsupported or partial input is visible in the result; it is never silently treated as success.
