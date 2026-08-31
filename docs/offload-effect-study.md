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
