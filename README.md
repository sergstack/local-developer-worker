# Local Developer Worker

`ldw` produces deterministic, evidence-linked JSON for logs, tests, Git state, file inventory, context selection, and factual reports. It is a local CLI for Codex workflows, not an autonomous coding agent.

## Install and run

```bash
uv sync --extra dev
uv run ldw doctor
printf '%s' '{"text":"ERROR failed"}' | uv run ldw log parse

# Install once for all local Codex projects, then select the balanced policy.
uv tool install --editable .
mkdir -p ~/.config/local-developer-worker
cp examples/policies/balanced.toml ~/.config/local-developer-worker/policy.toml
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

`ldw log process` accepts raw log text, runs Stage A first, and routes only valid observed parsed events to Stage B. It bypasses semantic processing for short logs unless `semantic: true` is supplied, recognises repeated failure signatures, records source accounting and semantic attempt/acceptance/fallback state, and preserves the Stage A observed-event fallback if inference is unavailable or rejected. The balanced global policy has no allowed repository roots: `ldw git facts` and `ldw files inventory` remain blocked until a policy explicitly names the requested root.

## Wave 2 context and evidence

`ldw context pack` accepts an explicit allowed `repository_root`, caller-supplied safe candidate metadata, and deterministic task signals. Contract `2.0.0` keeps every considered inclusion and exclusion visible, labels candidate relevance honestly, reports byte reduction without claiming token savings, and supports bounded expansion linked to a previous package.

`ldw evidence build` accepts only supplied evidence. Contract `2.0.0` preserves per-item origin and source lineage, keeps missing tests visible, and emits resumable handoff state without asserting root cause.

```bash
printf '%s' '{"repository_root":".","task":"Inspect CLI","files":[{"path":"src/local_developer_worker/cli.py","size_bytes":9537}],"target_files":["src/local_developer_worker/cli.py"]}' | uv run ldw context pack
```

Use direct bounded reading instead for a short task with one known file. A root outside the active policy allowlist remains blocked. See `docs/wave-2-migration.md` for compatibility and expansion details.

## Safety

Repository, context, and evidence tools require an explicit allowed `repository_root`. The inventory and selector block secret-like paths and symlinks escaping that root. Git collection is read-only. Unsupported, low-benefit, or partial input is visible in the result; it is never silently treated as success.
