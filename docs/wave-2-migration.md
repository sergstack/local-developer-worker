# Wave 2 contract migration

Wave 2 adds payload contract version `2.0.0` to Context Package and Evidence Package data. The enclosing `ToolResult` remains version `1.0.0`.

## Context Package

Existing `included_files`, `excluded_candidates`, `budget`, `relevant_files`, and legacy `reasons` remain readable. Version 2 adds:

- explicit `repository_root` and `repository_root_explicit`;
- `selection_reason`, `evidence_source`, and `relevance_status` for every included file;
- `reason_code` and `policy_rule` for every excluded file;
- byte-volume metrics and visible `selected`, `low_benefit_bypass`, or `unsupported` status;
- `mode=expand` with a full previous `ToolResult`, matching `previous_run_id`, requested paths, added files, and still-excluded paths.

The public CLI now requires a repository root allowed by the active policy. Legacy direct Python calls without a root remain readable but return `partial` with `legacy_implicit_repository_root`.

## Evidence Package

Existing task, repository state, observed log/test results, file inventory, missing evidence, open questions, tool versions, and content hash remain readable. Version 2 adds:

- per-item lineage and controlled origin values;
- separate observed, deterministic-derived, and model-derived-candidate collections;
- explicit test and Git provenance rules;
- context-package linkage;
- resumable objective, state, considered files, tests, failures, constraints, missing evidence, and next bounded action.

Packages with missing lineage remain visible as `partial`; unsafe paths or unsupported root-cause conclusions are rejected.

## Rollback

Callers can stop using `mode=expand` and continue consuming the legacy context/evidence fields. A code rollback may restore the previous payload implementation while retaining this migration note, frozen fixtures, and evaluator evidence. No rollback requires changes to Stage B, global configuration, external repositories, or mutating Git commands.
