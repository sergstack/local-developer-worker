# Global Codex integration

Status: `active_via_equivalent_global_rule`. The global Codex instructions contain the accepted context-pack/evidence-build workflow with the same bounded intent.

```text
For multi-file or repository-discovery tasks, use `ldw context pack`
before broad repository reading.

Use `ldw evidence build` for resumable task state, handoff, Judge review,
and final execution reporting.

Treat file relevance as candidate relevance unless supported by explicit
or deterministic dependency evidence.

Request bounded context expansion when critical context is missing instead
of reading the full repository.

Never include sensitive files without explicit authorization.
```

Bypass Wave 2 when one explicitly named file is sufficient, the task is short and obvious, repository discovery is unnecessary, context preparation costs more than direct bounded reading, or a security-sensitive task requires Codex-only handling.
