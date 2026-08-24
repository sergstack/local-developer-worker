# Adaptive Codex Routing effect study

This is the forward, **measurement-only** protocol for determining whether
Adaptive Codex Routing provides an observable benefit in latency, provider
tokens, or selected context. It replaces neither routing correctness tests nor
the privacy-safe calibration journal.

## Boundary

`scripts/run_routing_effect_study.py` only analyses an already-sanitized JSON
manifest. It never starts Codex, reads an LDW session journal, modifies a
policy, changes a route, or writes a result. Its fixture is intentionally
`dry_run`; it is a contract test and can never promote a routing change.

Keep real-study data in an owner-controlled, ignored directory. Do not commit
raw task text, repository paths, prompts, source, provider responses,
credentials, thread IDs, or model identifiers. The manifest accepts only
opaque pair/snapshot IDs, task class, terminal/verification states, numeric
metrics, and context safety counters.

## Preregistered paired protocol

Use the same immutable repository snapshot, sanitized task, read-only sandbox,
verification command, and no explicit profile/model/effort override for each
matched workload. The only arm difference is routing mode:

- **control:** a temporary study-only policy with `adaptive_routing = false`
  and `default_profile = "balanced"` (Terra / medium under the current
  personal policy);
- **adaptive:** the current personal policy with `adaptive_routing = true`.

Direct both real-study invocations to a separate `LDW_SESSION_LOG_DIR`; do not
mix them into the calibration journal. Record one terminal execution per arm.
The model findings remain outside LDW's ToolResult contract and must not be
used as a semantic-quality score without a separately approved blind review.

Begin with a 12-pair instrumentation pilot. It checks capture and pairing only.
The live decision set is at least 30 matched pairs, with at least ten in each
of routine/read-docs, bounded-debug, and cross-cutting/high-risk strata.
Report class-specific results only at 20 or more completed pairs for that
class.

## Metrics and gates

For every pair, capture latency, `input_tokens`, `cached_input_tokens`,
`output_tokens`, `reasoning_tokens`, fallback/escalation counts, terminal and
verification status, candidate/selected context bytes, critical-file recall,
and sensitive-block count.

`provider_total_tokens = input_tokens + output_tokens`. Cached input is a
subset of input and reasoning-token inclusion in output is unknown, so neither
is added again. They remain diagnostic metrics.

The runner uses deterministic paired bootstrap intervals (10,000 resamples).
A live promotion candidate requires all of the following:

- at least 30 complete matched pairs;
- critical recall exactly 1.0, zero sensitive-block failures, and no incomplete
  pair;
- at least one material benefit: median paired latency or provider-total-token
  reduction of 15% or more, or selected-context-byte reduction of 30% or more;
- for the claimed benefit, the upper bound of the paired 95% bootstrap interval
  is below zero.

The result is `REVISE` when safety holds but no benefit gate is met, and `STOP`
when safety/completion fails. It does not price tokens or claim USD savings.
Calibration remains offline, defaults to no policy mutation, and is not driven
by this runner.

## Reproducible dry run

```sh
PYTHONPATH=src python3 scripts/run_routing_effect_study.py \
  fixtures/routing_effect_study/dry_run_manifest.json
```

Expected result: `gate_status: INFORMATIONAL_ONLY` and
`verdict: INSUFFICIENT_EVIDENCE`. That proves the study contract and arithmetic,
not a production routing benefit.
