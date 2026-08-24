# Adaptive Codex Routing v2 calibration

Calibration is an opt-in, offline analysis layer over privacy-safe
`codex_routing_event_v2` records. It does not invoke a provider, change the
active policy, alter aliases, or grant execution authority.

## Commands

All commands read a JSON object from stdin. When using a personal runtime
policy from inside a repository, pass it explicitly:

```sh
printf '%s\n' '{"policy_path":"/Users/you/.config/local-developer-worker/policy.toml"}' | ldw routing stats
printf '%s\n' '{"policy_path":"/Users/you/.config/local-developer-worker/policy.toml"}' | ldw routing calibrate
```

`ldw routing stats` reports aggregates by task class, initial profile, and
initial effort. It includes sample size, observed first-pass verification rate,
under-routing (observed escalation) rate, over-routing candidate rate,
fallback/failure rates, verified-task token and latency medians, and
profile/effort distributions.

Statistics are separated by the complete revision identity: policy, generic
routing, alias/model mapping, and routing-taxonomy revisions. Mixed revisions
are explicitly marked; they are never silently pooled into a recommendation.

`ldw routing calibrate` produces either `keep`, `insufficient-evidence`, or a
traceable candidate revision. A candidate has
`acceptance_status: pending_human_acceptance`; it is never applied by LDW.
Each candidate has its parent/rollback target, reason, evidence period,
affected task classes, thresholds, and a deterministic revision ID. Its replay
compares current/candidate profiles with observed escalation, verification,
tokens, and latency only. Every counterfactual outcome is explicitly
`unverified`.

`ldw routing explain` resolves one proposed route from the supplied task and
policy, returning the generic profile, alias, effort, deterministic risk floor,
signal code, escalation path, and policy-revision hash. It does not return a
concrete model identifier.

## Calibration policy

The optional `[codex.calibration]` table is validated with the surrounding
Codex policy. Defaults are conservative and `enabled = false`:

```toml
[codex.calibration]
enabled = false
min_samples = 20
strong_sample = 50
max_age_days = 90
under_routing_escalation_rate = 0.35
under_routing_first_pass_rate = 0.80
over_routing_first_pass_rate = 0.95
```

Samples below 20 are insufficient; 20–49 candidates are marked `weak`; 50 or
more are `eligible`. Evidence of escalation or poor observed first-pass
verification can propose a stronger profile. A lower-profile proposal requires
observed verified success for that lower profile and cannot go below the most
restrictive deterministic risk floor observed for the population. Failed and
unverified records are never treated as successful evidence.

`min_samples` and `strong_sample` count independent, calibration-eligible
routing runs, not provider attempts. A v2.3+ record is eligible only after a
real Codex model execution reaches a terminal model event. Policy/preflight,
configuration, authentication, capability, or launch blocks remain available
as operational records but do not increase calibration population `n`. One
eligible terminal `ldw codex run` record is one observation; an
exact-session escalation such as Terra → failed verification → Sol → passed
remains one observation, with its final profile and escalation count. Duplicate
JSONL records emitted by the current v2.4 contract have a privacy-safe random
`execution_id`; the deterministic public `run_id` is an input fingerprint and
may legitimately repeat across actual executions. Duplicate records with one
`execution_id` and complete revision identity are deduplicated. Conflicting
records inside that same execution identity are quarantined and do not enter
calibration. Legacy records without `execution_id` retain the conservative
`run_id` identity rule. Reusing a deterministic `run_id` after a policy,
routing, alias, or taxonomy revision is not a conflict; revision isolation
keeps the observations separate.

`max_age_days` is evaluated from the append-only journal partition date. Older
observations are reported as stale and excluded from `routing calibrate`. The
current candidate population additionally must match the active policy,
routing, alias, and taxonomy revisions, so old models, aliases, or taxonomy
cannot dominate a new configuration.

## Telemetry boundary

The current v2.3 record is an exact allowlist: record type/version, opaque LDW
run ID, base task class, signal code, routing disposition, nullable requested
override profile, override state, adaptive/fixed mode, risk floor, initial/final
generic profile and effort,
fallback/escalation counts, first/final verification status, terminal status,
nullable token counters, latency, and policy-revision hash. It excludes task
text, prompts, source code, file paths, commands, concrete model IDs, provider
responses, thread/session IDs, credentials, and secrets.

It also stores opaque hashes for routing, alias/model-mapping, and taxonomy
revisions. These hashes contain no model prompt, task, path, source, provider
output, or credential.

`calibration_eligible` is the explicit v2.3 population gate. Existing v2.1 and
v2.2 records remain readable; legacy records are eligible only when they show a
verified terminal pass with observed input and output tokens. This conservative
rule prevents old policy-blocked records from entering calibration.

Token semantics are versioned as follows: provider `input_tokens` is inclusive
of `cached_input_tokens`; `non_cached_input_tokens = input_tokens -
cached_input_tokens`; canonical `provider_total_tokens = input_tokens +
output_tokens`. `reasoning_output_tokens` remains a separate diagnostic with
`reasoning_in_output_status = unknown` and is never added again to the
canonical total. Aggregate output uses
`median_provider_total_tokens_per_verified_task` plus separate input, cached,
non-cached, output, and reasoning medians.

The base task class and matched signal are preserved when an explicit override
is accepted or rejected and when adaptive routing is disabled. Existing v2.1
records remain readable; calibration normalizes their legacy `task_class` to
the internal base task class without rewriting the append-only journal.

The calibration rollback is `[codex.calibration].enabled = false`; routing and
execution continue independently. Their controls are
`[codex].adaptive_routing = false` and `[codex].enabled = false`.
