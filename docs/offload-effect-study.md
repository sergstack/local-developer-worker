# Matched offload effect study

`ldw offload evaluate` is a deterministic, read-only analyzer for a caller-supplied
matched-task manifest. It does not run control or candidate routes: an owner captures
their already-sanitized aggregate observations, then passes them to this command.

Each pair uses an opaque `match_id` instead of an actual task identifier and includes
only an abstract `task_class`. The exact field allowlist rejects task text, paths,
prompts, outputs, provider responses, and unknown fields. Every arm records its
abstract route, terminal and verifier status, acceptance where available, latency,
provider input/output tokens, context bytes, local-compute milliseconds, fallback and
escalation counts, a controlled failure code, and policy revision hash.

For a binary gold result, the report counts false accepts and false rejects separately
for control and candidate. For a verifier-only task it reports acceptance and verifier
status without inventing a gold error rate. The export also reports observed matched
pair counts, median candidate-vs-control percentage deltas, candidate local-compute
burden, failures, and explicit limitations.

```bash
PYTHONPATH=src python3 -m local_developer_worker.cli offload evaluate \
  < fixtures/offload_effect_study/dry_run_manifest.json
```

Synthetic or dry-run data always returns `INSUFFICIENT_EVIDENCE`. Observed live data
with fewer than three complete pairs also remains insufficient; a candidate gold
disagreement returns `STOP`. Even a sufficient clean data set reaches only
`READY_FOR_AI_OS_REVIEW`. The output's `promotion_authority` is always `ai_os_only`:
LDW never changes routing, policy, or eligibility. The `evidence_export` block is the
stable, source-free packet AI-OS may reference in its own decision process.

## Matched task capture v1.1

Contract `1.1.0` keeps v1 readable and extends this existing analyzer for #62. It
adds opaque matched-environment, budget, timeout, verifier, acceptance-contract, and
arm-order fields. Each arm may record nullable provider cost/tokens and local compute,
plus observed context expansion, compaction/rereads, agent/LDW tool calls, corrections,
preliminary attempts, fallback, escalation, route/profile, and controlled overhead
reasons. `null` remains unavailable; it is never converted to zero.

The analyzer exports every opaque pair outcome and reason code. Candidate task-success
regression or a disagreement with a supplied gold acceptance is `STOP`; missing
required end-to-end observations produce visible `MEASUREMENT_INCOMPLETE`. It still
neither runs either arm nor promotes a route.
