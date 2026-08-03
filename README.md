# Local Developer Worker

`ldw` produces deterministic, evidence-linked JSON for logs, tests, Git state, file inventory, context selection, and factual reports. It is a local CLI for Codex workflows, not an autonomous coding agent.

## Install and run

```bash
uv sync --extra dev
uv run ldw doctor
printf '%s' '{"text":"ERROR failed"}' | uv run ldw log parse
```

All commands accept one JSON object on stdin and write one versioned JSON envelope to stdout. Diagnostics are written to stderr. The default policy blocks network access, edits, commits, merges, deployments, and semantic-model capabilities.

## Safety

Repository tools require an explicit `repository_root`. The inventory blocks secret-like paths and symlinks escaping that root. Git collection is read-only. Unsupported or partial input is visible in the result; it is never silently treated as success.
