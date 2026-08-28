# Local Ollama advisory suitability study

## Decision boundary

This study determines whether a small local model may be used for a specific
task class. It does not evaluate, route, or replace Codex. A syntactically
valid Ollama response is not task success.

The required matched measurements are:

| Metric | Definition | Pass condition |
| --- | --- | --- |
| Development speed | End-to-end wall-clock time, including Ollama and every Codex/human validation step | Candidate median is at least 10% lower |
| Codex token economy | `codex_input_tokens + codex_output_tokens`; local-model tokens remain separate because tokenizers are not comparable | Candidate median is at least 15% lower |
| Context cleanliness | Bytes supplied to Codex after the candidate path; required context must still be accepted by the verifier | Candidate median is at least 15% lower |

Both arms use the same frozen task, revision, verifier, budget, timeout, and
acceptance rule. Every pair must pass. Store only opaque IDs and aggregate
counts; never persist prompts, source, paths, tool arguments, model outputs, or
transcripts.

`ollama_input_tokens`, `ollama_output_tokens`, and `ollama_latency_ms` are
diagnostic aggregates only. They may be `null` when the safe adapter cannot
observe them; `null` is never treated as zero. Only observed Codex provider
tokens participate in the token-economy gate.

## Task classes

`terminal_deterministic` is the only class that can receive `PERMIT`: the
Ollama result must be consumed by a deterministic verifier and must not require
Codex to inspect its semantic content. Typical candidate: batch triage that
produces a bounded structured work queue, whose fields are fully checked by a
predefined validator.

At least five matched live pairs are required for every task class. A fast
single run remains `INSUFFICIENT_EVIDENCE`.

`codex_review_required` is always `DENY` for this optimization. Examples:
one-off code review, debugging hypotheses, architecture choices, generated
patches, or summaries used to make an engineering decision. If Codex must read
and judge the local answer, its review latency, tokens, and context are part of
the candidate arm; an unmeasured second loop cannot be called a saving.

For deterministic transformations, prefer ordinary code over an LLM. The local
model is considered only when the task is genuinely semantic, high-volume, and
the terminal verifier is sufficient.

## Execution protocol

1. Freeze at least five opaque, representative tasks per class and their
   deterministic verifier.
2. Run one Codex-only control and one candidate execution for each task in
   isolated worktrees under the same budget and timeout.
3. Record aggregate arm counts only. Candidate latency starts before the Ollama
   call and stops after the final verifier; it includes any Codex review.
4. Feed the sanitized manifest to `analyze_manifest`. A `dry_run` fixture is
   intentionally non-promoting; only owner-authorized `live` evidence with
   `evidence_status: observed` can yield `PERMIT`. Live invocations over a
   synthetic fixture remain non-promoting.
5. Retain failed pairs and outliers. Any acceptance failure or a missed metric
   denies the class; do not generalize a single fast run.

## Current evidence

Five synthetic local advisory calls established a 2,064 ms median local cost
and structured-output containment. They had no matched Codex control or
task-success verifier, so they authorize no task class; see
`docs/ollama-advisory-microbenchmark-2026-08-28.md`.

The related five-task Context Efficiency replay is also not evidence that
Ollama advisory improves coding work: its candidate reduced context but missed
the required tool-call and latency gates. It reinforces the rule that a smaller
context alone is insufficient.

| Task class | Current decision | What is proved |
| --- | --- | --- |
| One-off code review, debugging, design, or generated changes | `DENY` | Codex must inspect the semantic result; its review is an additional candidate-arm step, so an unmeasured or unchanged review cannot be presented as a saving. |
| Exact parsing, normalization, duplicate detection, or other deterministic transformation | `DENY` for Ollama optimization | A deterministic implementation has no model round trip and remains the correct baseline. |
| High-volume semantic batch triage with a terminal deterministic verifier | `INSUFFICIENT_EVIDENCE` | It is the only candidate shape: a small, schema-bounded result may be consumed without Codex semantic review. Five live matched pairs must still clear all three gates. |

Therefore the currently evidence-backed production allowlist is empty. This is
an intentional safety and performance conclusion, not a disabled feature being
described as a benefit.

The synthetic terminal-triage pilot did clear all three numerical gates on five
pairs with no acceptance regression, establishing the technical candidate shape
without promoting it to real repository work. See
`docs/ollama-advisory-synthetic-pilot-2026-08-28.md`.

## Reproducible dry run

```sh
PYTHONPATH=src python3 scripts/run_ollama_advisory_study.py \
  fixtures/ollama_advisory_study/dry_run_manifest.json
```

The expected result is `INSUFFICIENT_EVIDENCE` for every class. That validates
the contract; it is not a claim of a production benefit.
