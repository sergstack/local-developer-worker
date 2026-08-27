# Context-efficiency measurement contract

Issue #23 establishes the fixed offline baseline used by the Context Efficiency vNext child issues. It measures the current selection behavior only; it does not change context selection, routing, expansion, or any public CLI contract.

Run the baseline from the repository root:

```sh
PYTHONPATH=src python scripts/run_reference_benchmark.py
```

The output validates against `schemas/context_efficiency_measurement.schema.json`. It records the current Git commit, whether the worktree was clean, the runner hash, and the SHA-256 hash of `benchmarks/task_manifest.json`. Those identifiers make a before/after comparison valid only when the same corpus and source revision are intentionally selected.

Each per-case metric declares one of four statuses:

- `observed`: obtained directly from the fixed fixture or an offline runner invocation;
- `estimated`: computed by a documented estimator;
- `unavailable`: the quantity would require evidence not available in this offline run;
- `not_measured`: this baseline does not attempt to collect the quantity.

Context byte totals, file counts, expansion count, and runner latency are observed. `estimated_input_tokens_*` use the explicit `ceil(bytes / 4)` estimator and are not provider- or Codex-measured token counts. Provider token and cost evidence are unavailable because the baseline makes no provider calls. Coding-agent tool calls and task-success/acceptance are not measured by this offline selection-only corpus.

The existing summary fields remain for compatibility. Their context-reduction figures are descriptive baseline evidence only: they do not claim token savings or authorize an optimization. Later children must compare the same corpus and report observed values separately from estimates and unavailable data.
