# Local Developer Worker

Local Developer Worker (`ldw`) is a deterministic, read-only evidence layer
for coding agents. It helps an agent work with less irrelevant context, retain
an auditable chain of evidence, and distinguish observed results from guesses.

It is **not** an autonomous coding agent and it does not replace Codex. LDW
does not edit repositories, commit, merge, deploy, or silently turn an
incomplete check into success.

## Why use it

LDW is most useful when a task is large enough that process mistakes become
expensive:

- select a bounded, explainable repository context instead of reading broadly;
- establish test outcomes from captured runner output;
- preserve Git facts, verifier results, and open questions for review or
  handoff;
- make release gates resumable and detect evidence that became stale after a
  revision changes;
- keep optional local-model assistance tightly bounded and privacy-aware.

For a one-file question or a trivial edit, direct reading is normally faster.

## What it does

| Need | LDW command | Result |
| --- | --- | --- |
| Verify the local setup | `ldw doctor` | Capability and policy status |
| Establish test status | `ldw test parse` | Observed pass/fail evidence |
| Inspect repository state | `ldw git facts` | Read-only branch, diff, and revision facts |
| Select code context | `ldw context pack` | Bounded files with selection and exclusion reasons |
| Compact working context | `ldw context compact` | Exact declared state plus a non-authoritative candidate summary |
| Preserve task evidence | `ldw evidence build` | Source-linked evidence and resumable state |
| Review a release portfolio | `ldw portfolio verify` | Complete gate reconciliation, including failures |
| Inspect process health | `ldw telemetry summary` | Privacy-safe local aggregates |
| Route an isolated Codex run | `ldw codex run` | Opt-in routing and execution metadata |
| Ask a local Ollama model | `ldw ollama advise` | Opt-in, read-only structured advisory |
| Execute an AI-OS offload envelope | `ldw offload execute` | Caller-owned route, capability, fallback, and provenance result |
| Analyze matched offload evidence | `ldw offload evaluate` | Privacy-safe evidence export for AI-OS review only |
| Validate a candidate lesson | `ldw learn validate-candidate` | Schema and opaque-evidence lineage only; never promotion |

All commands read one JSON object from stdin and return one versioned JSON
`ToolResult` on stdout. Diagnostics go to stderr.

## Install

```bash
uv sync --extra dev
uv run ldw doctor

# Optional: install the CLI once for all local projects.
uv tool install --editable .
mkdir -p ~/.config/local-developer-worker
cp examples/policies/balanced.toml ~/.config/local-developer-worker/policy.toml
```

The repository policy is intentionally restrictive. After copying the balanced
policy, add the exact repository root you intend LDW to inspect under
`[security].allowed_repository_roots`; an empty list is a deliberate block.
For personal usage, pass an explicit policy path or set `LDW_POLICY_PATH`; the
active policy remains the authority for repository roots, network access, model
calls, and adapters.

## Recommended workflow with Codex

Use the lightest tool that fits the task:

1. For a short task with one known file, read it directly.
2. For unfamiliar or multi-file work, build a `context pack` from an explicit
   allowed repository root.
3. Run tests through the supplied capture-and-parse wrapper, so the test
   result is observed rather than inferred.
4. Before a PR, merge, or handoff, collect `git facts`, build evidence, and
   run the relevant portfolio gates.

Example context request:

```bash
printf '%s' '{"repository_root":".","task":"Inspect CLI behavior","files":[{"path":"src/local_developer_worker/cli.py","size_bytes":9537}],"target_files":["src/local_developer_worker/cli.py"]}' \
  | uv run ldw context pack
```

Example authoritative test capture:

```bash
/Users/sst/.codex/skills/local-developer-worker/scripts/run_and_parse_tests.py \
  -- uv run python -m pytest -rA
```

`ldw test parse` reports only what the runner output establishes. A partial,
blocked, unsupported, invalid, or timed-out result is never a passing check.

## Context efficiency

`ldw context pack` makes context selection explicit: every retained path has a
reason and every rejected candidate has a controlled exclusion reason. It
reports byte-based reduction, not token savings; token or latency savings must
come from a matched measurement study.

Use `mode=expand` to request a bounded addition to a prior package instead of
restarting a repository-wide scan. The packer repeats root, symlink, secret,
binary, generated-file, and size-limit checks on each expansion.

`ldw context compact` is deterministic: callers supply the preservation set
and any candidate summary. It preserves the declared goal, constraints, IDs,
authority, acceptance, evidence, unknowns, no-repeat actions, and resume refs
exactly, or returns a visible non-success result. It never invokes a model or
turns a summary into source evidence.

See [the tool contracts](docs/tool-contracts.md) and
[Wave 2 migration guide](docs/wave-2-migration.md) for the versioned contract.

## Quality and release evidence

`ldw portfolio verify` runs every declared gate independently and continues
after a failure, so the output shows the complete state rather than the first
problem only. `ldw portfolio status` marks saved evidence stale when the
commit or workspace fingerprint changes.

```bash
uv run ldw portfolio verify
uv run ldw portfolio status
uv run ldw telemetry summary --from-date 2026-08-01 --to-date 2026-08-31
```

Telemetry is local and privacy-safe: it does not retain source text, logs,
prompts, secrets, or provider responses.

## Optional Codex routing

`ldw codex run` is disabled until its policy explicitly permits it. It selects
a configured routing profile for an isolated advisory run and returns routing,
execution, verification, and token metadata. It does **not** return the child
model's answer and a passed execution verifier is not a semantic-quality
verdict.

```bash
printf '%s\n' '{"repository_root":".","policy_path":"/Users/you/.config/local-developer-worker/policy.toml","task":"Review the README","verification":{"kind":"execution"}}' \
  | uv run ldw codex run
```

Enable this only after configuring the exact executable, supported model
aliases, network policy, and verifier commands. Details are in
[Adaptive Codex Routing](docs/adaptive-codex-routing/SPEC.md).

## Policy-owned local offload

`ldw offload execute` accepts a caller-owned envelope containing `task_class`,
`risk_floor`, `offload_mode`, `verification_kind`, `fallback_policy`, and an
immutable `policy_revision`. LDW validates and executes that route; it does not
classify the task, promote a class, or alter authority. A successful local
response remains a `candidate_only` result with local-model provenance.

Local inference is optional. If its runtime or requested model is unavailable,
the command consumes an explicitly supplied successful deterministic ToolResult
first, invokes the authorized frontier route second, or returns a visible block.
It never installs, starts, or pulls Ollama or silently changes the policy mode.

The core feature adds no Python dependency. Local execution uses the configured
Ollama `/api/generate` endpoint only after the existing loopback and local
listener/process checks pass; a model-not-found response is reported separately
from runtime unavailability. Enable it with `[ollama].enabled = true` and
`[automatic].ollama_readonly_advisory = true`. Setting either flag to `false`
disables the local path without affecting deterministic commands. Frontier
fallback additionally requires the existing `ldw codex run` policy and an
allowed repository root. That flag change is the rollback; no evidence migration
or Ollama lifecycle action is required.

## Matched offload evaluation

`ldw offload evaluate` analyzes an explicitly supplied, sanitized matched-pair
manifest. It never executes either arm, reads telemetry, or decides promotion.
The report records opaque matched task IDs, route/verifier/acceptance outcomes,
latency, provider-token and context deltas, local-compute burden, fallbacks,
escalations, controlled failures, and available false accept/reject counts. Its
highest result is `READY_FOR_AI_OS_REVIEW`; only AI-OS can make a promotion
decision. See the [study contract](docs/offload-effect-study.md).

## Optional local Ollama advisory

`ldw ollama advise` is a separate, read-only advisory boundary for a small
local model. It has no repository access, tool execution, or write capability.
It accepts an explicitly supplied bounded task, requires both
`[ollama].enabled = true` and
`[automatic].ollama_readonly_advisory = true`, and permits only a verified
loopback Ollama runtime.

Only a schema-validated `summary` and up to five `next_actions` cross the
boundary. Raw prompts, envelopes, and model responses are not retained.

`ldw doctor` reports only the optional local-inference capability state:
`available`, `model_unavailable`, `unavailable`, `incompatible`, or
`policy_blocked`. Runtime and model availability are separate. Doctor never
starts Ollama, installs it, or pulls a model; absence leaves all deterministic
LDW commands available under their own policies.

The currently supported use is narrow: high-volume semantic terminal triage
whose small output is fully consumed by a deterministic verifier. Do not use
it for code review, debugging hypotheses, architecture, generated patches, or
any workflow where Codex must semantically review the local answer.

### What the pilot measured

A five-pair **synthetic** terminal-triage pilot compared a Codex-only control
with `qwen3:8b` behind `ldw ollama advise` under the same deterministic marker
verifier:

| Measure | Control | Local candidate | Matched median delta |
| --- | ---: | ---: | ---: |
| Accepted pairs | 5 / 5 | 5 / 5 | No regression |
| End-to-end latency | 3,851–5,139 ms | 1,764–1,967 ms | **-54.1937%** |
| Codex provider tokens | 16,824–16,826 / pair | 0 | **-100%** |
| Bytes presented to Codex | Control input | 0 | **-100%** |

This proves a technical shape, not a production benefit: the corpus is
synthetic, the local model's own token counts were not observed, and no real
repository task is currently promoted to the local-model allowlist. Read the
[study contract](docs/ollama-advisory-effect-study.md) and
[pilot record](docs/ollama-advisory-synthetic-pilot-2026-08-28.md) before
running a live study.

## Safety boundaries

- Repository, context, and evidence commands require an explicitly allowed
  repository root.
- Sensitive paths and symlinks escaping the root are blocked.
- Git collection is read-only.
- Non-loopback, ambiguous, proxy, tunnel, or unverified local inference
  endpoints are policy-blocked.
- Model-derived output remains a candidate; it is never silently elevated to
  observed evidence.
- The default policy blocks edits, commits, merges, deployments, network
  access, and semantic-model capabilities.

For precise input and output schemas, read
[docs/tool-contracts.md](docs/tool-contracts.md).
