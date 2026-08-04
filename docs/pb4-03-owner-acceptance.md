# PB4-03 owner acceptance package

Summary: Contract v2 achieves deterministic full accounting on the frozen five-case corpus. The prior qwen3.5:9b comparison ran through a Windows tunnel and is excluded from Mac-local model evidence; a separate 20-run evaluation verifies four exact models on the physical Mac listener at port 11435. The accepted PR #5/#6 prerequisite is now present in `origin/main`; PB4-03 is reconstructed from that base and preserves its timeout and policy guards.

Execution status: reconstructed from accepted prerequisite; MRG-05 re-acceptance complete after MRG-06 explicit-only enforcement
Repository: `/Users/sst/prod/Codex Tools`
Worktree: `/Users/sst/prod/Codex Tools-pb4-03`
Branch: `codex/pb4-03-deterministic-accounting`
HEAD: `048fc96c745c2aad25990f77b94cb3bd9daf8735`
Origin main: `048fc96c745c2aad25990f77b94cb3bd9daf8735`
Merge-base: `048fc96c745c2aad25990f77b94cb3bd9daf8735`

## Provenance

- accepted prerequisite: PR #5 and PR #6 are included in `origin/main` at `048fc96`; their audited `cli.py`, `policy.py`, balanced policy, benchmark manifest, Wave 2 files, and safety-matrix changes are retained unchanged.
- pb4-03-only changes: `src/local_developer_worker/stage_b_accounting.py`; the v2 additions in `stage_b_cluster.py` and `log_process.py`; the generic Stage A component correction in `tools.py`; `schemas/semantic_grouping_v2.schema.json`; the four PB4 evidence/corpus fixtures; both PB4 evaluator scripts; three PB4 test modules; fixture validation additions; migration, entry-gate, Mac-evaluation, and owner-acceptance documents; and PB4-03/PB4-04 registry records.
- dependency status: resolved for reconstruction; branch base and merge-base are the accepted `048fc96` prerequisite.
- reconstruction method: the pre-reconstruction dirty state is retained in a recoverable Git stash; the branch was recreated from `origin/main`, and only the recalculated PB4-03-only scope was reapplied.
- excluded prerequisite copies: `benchmarks/task_manifest.json`, `examples/policies/balanced.toml`, `src/local_developer_worker/cli.py`, and `src/local_developer_worker/policy.py` were not reapplied.
- conflict resolution: owner-approved v2 accounting was integrated over accepted `log_process.py`; `timeout_before_execution`, policy guards, and all other PR #5/#6 behavior remain in place. A dedicated timeout regression test proves transport is not called and all observed candidates fall back.
- candidate eligibility decision: owner selected PB4 v2; the parsed-only PR #5 guarantee is explicitly superseded for sanitized `unknown_event` candidates, while deterministic dispositions, bounded fields, validation, fallback, and explicit/policy bypasses remain enforced.
- routing decision: owner selected MRG-06(b), implementing PB3-01(b). Missing/false `[semantic].automatic_routing` blocks threshold/signature model calls; only payload `semantic: true` can route unless policy deliberately opts back in with `automatic_routing = true`.

## Files inspected

- source and PB4 worktree Git state, shared prerequisite files, global CLI installation, policy and schemas
- four retained `.repo_index/pb4` diagnostic artifacts
- Stage A parser, v1 cluster/validator, v2 accounting/process, tests, fixtures, governance, migration, and generated release gates

## Files changed

- bounded runtime: `src/local_developer_worker/{tools,stage_b_cluster,stage_b_accounting,log_process}.py`
- contracts/evidence: `schemas/semantic_grouping_v2.schema.json`, `fixtures/stage_b/pb4_v2_cases.json`, `fixtures/stage_b/pb4_compile_error_evidence.json`, `fixtures/stage_b/pb4_03_evaluation_evidence.json`
- validation: `scripts/run_pb4_03_evaluation.py`, `scripts/validate_fixtures.py`, PB4 Stage B tests, and the v2-updated accepted global-log-process tests
- governance/docs: `docs/gate_registry.json`, `docs/stage-b-entry-gate.md`, `docs/tool-contracts.md`, migration and this report

## Commands run

- required Git provenance and file-hash comparisons, including `git fetch origin main`
- retained artifact hash and safe structured inspection (raw response content was not emitted)
- identical-corpus v1, v2, and deterministic-fallback evaluator, twice
- focused and full pytest runs with status established through `ldw test parse`
- schema, fixture, release-gate, secret, compile, doctor, diff, global CLI, root-gate, and rollback checks

## Tests observed

- focused PB4/global-log-process acceptance set: 26 passed, established by `ldw test parse`
- combined Wave 2 and PB4 set: 34 passed, established by `ldw test parse`
- full suite: 177 passed, established by `ldw test parse`
- schema, fixture, generated release-gate, secret scan, compileall, and diff checks: passed
- Wave 2 evaluator: mandatory correctness remained passing; context reduction remained `INFORMATIONAL_ONLY`
- PB4 live corpus evaluator after routing enforcement: 20/20 valid runs through explicit `semantic: true`; corpus unchanged; evidence SHA-256 `6111ecc804f0da1024a24cc5ecb80db1d0858442e91ddf7cff9025725ff80a5c`
- pre-live Mac evidence reaggregation: byte-identical with `model_calls_performed: 0`

## Contract

- previous version: v1 full-accounting model contract (`groups` plus model-controlled `excluded`)
- implemented version: `semantic_log_grouping_contract: 2`, deterministic global accounting and candidate-only model responsibility
- public schema version: outer `ToolResult` remains `1.0.0`; the semantic data contract is explicitly nested and versioned as v2
- migration note: `docs/migrations/semantic-grouping-v1-to-v2.md`
- v1 compatibility: the legacy `ldw log cluster` path, v1 fixtures, validator tests, and `excluded` interpretation remain available; historical evidence is not rewritten

## Frozen corpus

- case A pytest: `c310e6aaeb24a44e373b48016958d46409b8744fbdc00a87902379b1e5afc194`
- case B compile-error: `e9402489bb93bfda597598acc3399a5c9d1f4af6705c311d97cca2312ed7e254`
- case C mixed: `f566a9e8d171a938ce1543462962cf13f3afa7d496807a103fdb35288d3920fd`
- case D CLI/build: `d6b98068b84d06a3b037ea05aa0e009975c08db86b8913a2984bcda7b1e2047f`
- case E application/validation: `6f8b0ccae8898779f2c407e06ab2537690430d5f69f3791311ba295d8462ee04`
- corpus file hash recorded by evaluator: `51a983b4ed07c70bcfff7a3caadfc711c397ee7b55b8767300f63d0532522f0b`
- artifacts preserved: all four original files remain under `/Users/sst/prod/Codex Tools/.repo_index/pb4/`; none were deleted
- compile source hash: `6bb4ada224b838e8737b36fc8a2367350b05e0233fa76fe263576ade5cf70791`; Stage A structure remains 6 total / 1 parsed / 4 unknown / 1 part-of-event; observed v1 omission remains `EV-000006`

## V1 results

- accounting: 5/5 outputs retain all 28 observed events; accepted candidates cannot contain invented, duplicate, or omitted accepted IDs
- accepted: 3; rejected: 2; fallback: 2
- false merges: 0; false splits: 2
- unclassified: NOT MEASURED (v1 has no deterministic disposition field)
- median latency: 4211 ms; maximum latency: 7170 ms
- operational usefulness: 3/5 by frozen required-pair/forbidden-merge judge

## V2 results

- accounting: 5/5 fully accounted; 28 observed events; 9 structural continuations; 2 deterministic exclusions; 0 unclassified; 0 policy-blocked in corpus
- accepted: 4; rejected: 1; fallback: 1
- invented accepted IDs: 0; duplicate accepted IDs: 0; omitted accepted candidate IDs: 0; fallback coverage: 100%
- false merges: 0; false splits: 1; catch-all groups: 0; needs-review groups: 0
- median latency: 3769 ms; maximum latency: 5635 ms
- operational usefulness: 4/5 by the same frozen judge
- compile-error case: rejected with `candidate_recall_failed` and preserved through deterministic fallback; no acceptance claim is made for that candidate

## Before/after

This section records the earlier v1/v2 functional comparison, but it is not Mac-local inference evidence: endpoint `127.0.0.1:11434` was an SSH tunnel to a Windows host. It is excluded from the four-model Mac comparison.

- full coverage: unchanged at 5/5
- acceptance-rate delta: +0.20
- fallback-rate delta: -0.20
- false-merge delta: 0
- false-split delta: -1
- review-burden delta: 0 observed `needs_review`; human review corrections NOT MEASURED
- median latency delta: -442 ms
- operational usefulness: +1 case

## Safety

- loopback only: preserved and tested
- raw response stored: false in the frozen evaluator and regression fixtures. The separately retained diagnostic artifact intentionally still contains its raw response and requires owner confirmation before deletion.
- previous qwen3.5:9b inference: loopback transport through a Windows tunnel; external internet inference was not observed, and Mac-local execution was false
- new four-model inference: physical Mac listener verified at `127.0.0.1:11435`; external internet inference was not observed
- code artifacts: disabled and tested
- shipped default: semantic execution remains off
- repository root gate: preserved; the globally installed CLI blocked a repository-sensitive call outside the explicit allowlist

## Governance

- registry: PB4-03 decision and `qa_pending` state recorded in `docs/gate_registry.json`
- entry gate: updated from stale planning-only language and records owner-acceptance requirements
- release gates: generated document check passes
- accepted prerequisite manifest and Wave 2 records remain unchanged
- locality gap: PB4-04 recorded as `not_started`; no production enforcement was implemented

## Rollback smoke

- status: passed
- evidence: `semantic: false` bypasses transport; Stage A output remains unchanged; forced model failure gives full observed fallback; v1 validator path remains covered; default policy remains off; migration documentation remains present; no raw response appears

## Acceptance matrix

| Requirement | Status | Evidence | Risk |
|---|---|---|---|
| Branch provenance reconciled | implemented | branch, origin/main, and merge-base are `048fc96`; recoverable pre-reconstruction stash retained | none observed |
| Five-case corpus frozen | implemented | corpus hashes and fixture validation | corpus is owner-reviewable but human corrections are not measured |
| Compile evidence preserved | implemented | source/sanitized hashes and v1 omission record | retained diagnostic artifact still contains raw response by owner request |
| Identical-input v1/v2 comparison | implemented | safe aggregate evidence, same model and Stage A events | available model was `qwen3.5:9b`, not the unavailable `qwen3:8b` |
| Full deterministic accounting | implemented | 5/5 cases and 100% forced fallback coverage | none observed in frozen corpus |
| Semantic usefulness not degraded | implemented | useful cases 3→4, false splits 2→1, false merges 0→0 | one compile candidate still falls back |
| v1 compatibility | implemented | legacy tests and full suite | routing-mode decision remains separate |
| Governance and rollback | implemented | validators and smoke tests | global-branch audit remains separate |

## Acceptance gates completed

- dependency/provenance reconciled against accepted PR #5/#6 base `048fc96`
- retained compile-error source and diagnostic artifacts located and hashed without emitting the retained raw model response
- five-case corpus hashes, dispositions, separations, and sensitive-content flags validated
- identical-input v1/v2/fallback aggregate evidence validated
- 20-run Mac-local evidence validated and reaggregated byte-identically without model calls
- 20-run Mac-local matrix repeated on reconstructed code with unchanged accounting, false-merge, false-split, and usefulness results
- migration, compatibility, governance, and rollback smoke validated
- focused and full tests established through `ldw test parse`; all required non-test checks passed

## Missing gates

- commit, push, PR, merge, and final owner review have not been performed

Assumptions: corpus-defined required pairs and forbidden merges are the acceptance judge for operational usefulness. Listener verification identifies the current Mac process and executable but is not cryptographic service attestation.

Missing evidence: human review corrections are `NOT MEASURED`; five cases are insufficient to establish a winning model; the separate full audit of `codex/stage-b-global-log-process` is outside PB4-03.

Risks: PB4 v2 intentionally broadens eligibility to sanitized `unknown_event` candidates; consumers requiring parsed-only behavior must use the legacy v1 command or disable semantics. A deliberate future `automatic_routing = true` policy change would restore threshold/signature calls and requires separate owner control. The earlier qwen3.5:9b comparison must not be cited as Mac-local evidence; the five-case Mac matrix does not establish a model winner.

Blockers: no PB4-03 publication or merge should proceed until the owner separately authorizes each Git action.

Commit: not run
Push: not run
PR: not run
Owner acceptance readiness: yes for reconstructed behavior and evidence
PB4-03 verdict: MRG-05 pass; MRG-06(b) implemented and reaccepted
