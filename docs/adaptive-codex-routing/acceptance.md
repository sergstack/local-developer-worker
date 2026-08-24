# Adaptive Codex Routing acceptance

## Scope and authority

This record documents the accepted Adaptive Codex Routing contracts and their
historical evidence. Current provenance belongs to Git history and the latest
fresh validation report; this document intentionally does not pin a branch,
working-tree state, commit SHA, or evergreen test count.

The live configuration is deployment-owned, operator-supplied, and intentionally
outside the repository. It keeps the generic classifier profiles, mapping them
as follows:

| Generic profile | Deployment alias | Concrete model | Selected effort |
|---|---|---|---|
| `efficient` | `luna` | `gpt-5.6-luna` | `low` |
| `balanced` | `terra` | `gpt-5.6-terra` | `medium` |
| `frontier` | `sol` | `gpt-5.6-sol` | `high` |

The local Codex model catalog reported all three concrete slugs. The policy
allows the current CLI family (`0.147`), has a validated acyclic alias fallback
graph (`luna → terra → sol`), and supports the configured low/medium/high
efforts. The implementation's v3 effort allowlist currently ends at `xhigh`;
the deployment policy does not claim `max` support.

## Offline evidence

| Requirement | Status | Inspectable evidence |
|---|---|---|
| Automatic routing classes and ordered deterministic signals | PASS | English and Russian structured/text/ambiguous cases in `tests/unit/test_codex_routing.py` |
| Policy-only aliases and effort compatibility | PASS | Alias replacement, unsupported effort, duplicate/cyclic fallback, floor/override tests |
| Concrete model and effort reach Codex CLI argv | PASS | Exact argv assertions in `test_argv_carries_resolved_model_effort_and_isolation` |
| Capability preflight and ambient-config isolation | PASS | Version plus `exec`/`resume` help checks; argv assertions for `--strict-config`, `--ignore-user-config`, `--ignore-rules` |
| Evidence-based exact-session escalation | PASS | Failed verifier resumes only the observed `thread-exact`, raises profile/model/effort, and never uses `--last` |
| No escalation after successful verification | PASS | `test_success_does_not_escalate` |
| Configurable escalation ceiling and model-unavailable fallback | PASS | Bound and missing-thread tests; stable pre-mutation model-unavailable fallback test |
| Verification authority | PASS | Read-only advisory execution verification for every route; write-capable mutation verifier required; exact policy argv/executable; tests interpreted with `command_observed=true` and observed exit code |
| Repository, network, and authority boundaries | PASS | Root gate, symlink/unlisted verifier rejection, direct argv, filtered environment, no automatic Git/deploy, and sandbox-network denial tests |
| Privacy-safe telemetry | PASS | `codex_run_event_v1` allowlist/schema, malicious extra-field drop, and aggregate summary tests |
| Fixed-profile and full-disable rollback | PASS | CLI disabled and `adaptive_routing=false` integration tests |
| Existing LDW compatibility | PASS | Canonical suite is required to pass through `ldw test parse` in each fresh acceptance run |
| Schema, TOML, compile, whitespace checks | PASS | Draft 2020-12 schemas, example TOML, compileall, CLI help, and `git diff --check` |

Offline tests prove the adapter contract; fake provider processes do not prove
provider availability, account authorization, or provider-side effective model
selection.

Focused and full-suite counts are deliberately not frozen here; use the latest
acceptance report and its `ldw test parse` run IDs.

## Final validation record

| Check | Status | Result |
|---|---|---|
| Deployment TOML plus routing-policy validation | PASS | Luna/Terra/Sol mapping accepted by `validate_codex_policy` |
| Focused Adaptive Routing tests | Required | Fresh result must be established through `ldw test parse` |
| Full canonical suite | Required | Fresh result must be established through `ldw test parse` |
| JSON schema parse and Python compile | PASS | All `codex_*.schema.json` parsed; `compileall -q src` succeeded |
| TOML parse | PASS | Deployment policy parsed by `tomllib` and validated above |
| `git diff --check` | PASS | No whitespace errors |
| PR-ready patch on clean HEAD snapshot | PASS | `git apply --check` succeeded in an isolated clean archive |

## Live evidence — controlled read-only smoke (2026-08-21)

These historical runs used `ldw codex run` with an explicit generic profile, a routine
read-only task, execution verification, and the deployment policy above. The
Codex sandbox was `read-only`, approvals were `never`, and model-generated
command network access was explicitly disabled. No prompt, source code,
provider response, or thread ID is retained in the telemetry below.
Because the profiles were explicit overrides, these smokes prove transport and
profile propagation only; they are not evidence that adaptive classification
selected Luna, Terra, or Sol automatically.

| Profile / alias / effort | LDW run | Result | Observed tokens (input / cached / output / reasoning) | Escalations / fallback |
|---|---|---|---:|---:|
| `efficient` / `luna` / `low` | `RUN-56f0fc0504a7ff9e` | PASS; verification passed | 41,107 / 25,088 / 281 / 226 | 0 / 0 |
| `balanced` / `terra` / `medium` | `RUN-28e24533de478b76` | PASS; verification passed | 17,566 / 11,008 / 163 / 141 | 0 / 0 |
| `frontier` / `sol` / `high` | `RUN-d6a31d2c80e0f133` | PASS; verification passed | 126,282 / 107,264 / 787 / 597 | 0 / 0 |

The first two CLI result records were directly observed. The frontier CLI
process produced no terminal record to the caller, so its result was recovered
only from the append-only, schema-validated `codex_run_event_v1` session
record; it is therefore included with that narrower evidence source rather
than inferred from process exit.

### Live JSONL and exact-session resume

A separate Luna/low controlled read-only session and one continuation were run
with the production argv builder. Both returned exit code 0 and JSONL event
types `thread.started`, `turn.started`, `item.completed`, and `turn.completed`.
The continuation used the exact `thread_id` observed in the first JSONL stream;
the identifiers matched and `--last` was absent. The same explicit model and
effort were reasserted on both commands.

| Phase | JSONL completion | Tokens (input / cached / output / reasoning) |
|---|---|---:|
| Initial Luna session | PASS | 16,130 / 9,984 / 75 / 66 |
| Exact-session resume | PASS | 32,365 / 25,088 / 82 / 66 |

The actual launched argv contract was observed as true for both commands:
`-m gpt-5.6-luna`, `model_reasoning_effort="low"`, `--strict-config`,
`--ignore-user-config`, `--ignore-rules`, and
`sandbox_workspace_write.network_access=false`. This is direct CLI propagation
evidence, not a claim that the provider echoed the selected settings.

The returned JSONL did **not** contain `model` or `reasoning_effort` fields.
Consequently, provider-echo confirmation of the effective Luna/Terra/Sol model
and effort is **NOT VERIFIED**, even though all three configured profile runs
received successful completed turns and token observations.

## Safety and privacy evidence

- Deployment configuration passes `validate_codex_policy`: provider transport
  has both required opt-ins (`network_access=true` and
  `codex.allow_network=true`), while `allow_write=false`, `sandbox=read-only`,
  and `approval_policy=never` remain enforced.
- Ambient Codex user config and rules were isolated for the live resume check.
- Telemetry contains only profile/alias/effort, terminal/verification status,
  escalation/fallback counts, and token counters. It excludes concrete model
  IDs, task text, prompts, source code, paths, commands, provider responses,
  secrets, and thread IDs.
- Successful live runs had zero escalation and fallback. Live forced-failure
  escalation and live model-unavailable fallback were **NOT RUN**; those remain
  offline-contract evidence only, avoiding unnecessary provider retries.

## Verdict

**PASS for the implemented offline contract and the three controlled
read-only live profile smokes.** Actual provider-side effective
model/effort echo remains **NOT VERIFIED** because the observed JSONL contract
does not expose those fields. This is not a production-readiness claim.

## Remaining evidence gap

Obtain provider-side model/effort attestation (or a documented Codex JSONL/API
field that exposes it) before claiming full live model-switch verification.

## v2 calibration review — offline acceptance

| Invariant | Status | Evidence |
|---|---|---|
| Policy/revision isolation | PASS | Versioned telemetry carries policy, routing, alias, and taxonomy revision hashes; mixed records are separated and incompatible records excluded from calibration. |
| Independent-task sample counting | PASS | One calibration-eligible terminal `ldw codex run` record is one observation; blocked/non-executed records are excluded, duplicate same-run records deduplicate, and conflicting same-run records are quarantined. |
| Temporal/model drift | PASS | Policy-configurable `min_samples`, `strong_sample`, and `max_age_days`; stale and incompatible observations cannot form a candidate. |
| Active-policy mutation | PASS | Calibration creates only a pending-human-acceptance candidate revision. |

The v2 review is offline evidence only. It does not change the earlier live
provider evidence or provider-side model/effort status.
