# Semantic grouping v1 to v2

V1 made the model responsible for global observed-event accounting: it received all Stage A events and returned `groups` plus model-controlled `excluded`. V2 moves event existence, deterministic disposition, candidate selection, validation, fallback, and final reconciliation into deterministic code. The model receives only `candidate_events` and returns `groups` plus `ungrouped_candidate_ids`.

V2 output is marked `semantic_log_grouping_contract: 2`. Final dispositions are `semantic_group`, `semantic_ungrouped`, `structural_continuation`, `deterministically_excluded`, `policy_blocked`, `fallback_observed`, and `unclassified_observed`. V2 does not generate the legacy model-controlled `excluded` field.

V2 intentionally supersedes the PR #5 parsed-only model-input guarantee. A sanitized `unknown_event` is no longer discarded from semantic eligibility solely because Stage A could not assign a richer parser state: deterministic code first records it as observed, assigns an explicit disposition, and may pass only the bounded candidate fields and stable event ID to the model. Candidate validation and final reconciliation still reject invented, duplicated, or omitted IDs and preserve the full observed fallback. `semantic: false`, disabled policy gates, policy-blocked content, and deterministic exclusions continue to bypass model transport.

`ldw log cluster` keeps V1 read and validation compatibility. `ldw log process` selects V2 and retains the outer `ToolResult` schema version `1.0.0`; the versioned semantic data contract is nested in `data`. Consumers that understand only V1 should continue using `ldw log cluster`. Historical V1 evidence is not relabeled or rewritten as V2 evidence.

PB3-01(b) manual-per-call routing is enforced in V2. When `[semantic].automatic_routing` is absent or `false`, event count and repeated signatures cannot start model transport; the payload must contain `"semantic": true`. A deliberate policy value of `automatic_routing = true` is the only way to restore threshold/signature routing. Both repository profiles set the field to `false`.

Roll back by setting `[semantic].enabled = false`, setting `[automatic].semantic_log_clustering = false`, passing `semantic: false`, or using the legacy V1 command. Stage A and the shipped default-off policy remain unchanged; V2 fixtures, migration notes, and safe evaluation evidence remain available. Neither runtime contract stores raw provider responses.
