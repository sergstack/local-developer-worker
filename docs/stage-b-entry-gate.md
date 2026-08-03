# Stage B entry gate

Stage B remains planning-only. `policy.toml` continues to keep semantic execution disabled, and no Stage B code may begin until Stage A is merged and explicitly accepted; local passing tests alone do not open this gate.

## Bounded first task

The first candidate is bounded clustering of repeated log messages: group already-observed lines that express the same recurring failure pattern and attach a count. The model may only receive sanitized Stage A log events, may not diagnose root cause, edit code, choose architecture, or invent missing lines, and must fall back to the ungrouped events when the contract cannot be satisfied.

## Evidence contract

Every semantic group must contain a stable candidate ID, `confidence`, and one or more `source_span` references to the Stage A events from which it was derived. Downstream output must label the group as **model-derived**, never as an **observed fact**. `report summarize` must keep model-derived candidates separate from observed facts and must preserve missing evidence and uncertainty.

## Regression gate before code

Before the first Stage B implementation line, define a sanitized reference set and executable gates for: source-span recall, zero invented sources, deterministic fallback, privacy preservation, explicit model-derived labeling, confidence bounds, and unchanged facts-only Stage A reports. The gate must reject any candidate lacking a valid source span or crossing the permitted semantic-task boundary.

## Stage A invariants

All guarantees `SA-01–SA-16` remain invariants. Stage B may neither weaken them nor reinterpret advisory SA-16 as architectural. In particular, it must preserve schema-valid envelopes, full log-line accounting, no false passed claims, sensitive-file blocking, read-only Git facts, policy denial of network/mutation/deployment, and facts-only reporting.
