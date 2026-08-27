# Context Efficiency vNext final acceptance study (#29)

## Verdict: REVISE

The final candidate revision was measured on the immutable #23 12-case corpus on 2026-08-28. The corpus remains valid and repeatable, but it is selection-only evidence: it cannot establish a matched before/after coding-agent task-success, tool-call, or latency result. Therefore the #29 PASS rule is not met and parent #22 must not be closed from this evidence.

## Observed matched evidence

| Measure | Result | Status |
| --- | ---: | --- |
| #23 cases | 12 | observed, immutable corpus |
| candidate context bytes | 765,530 total; median 63,920 | observed by the #23 runner |
| estimated input tokens before/after | 191,517 / 32,635 total | estimate (`ceil(bytes / 4)`), not provider tokens |
| provider tokens / cost | unavailable | no provider calls |
| coding-agent tool calls | not measured | no agent-attempt trace |
| task success / acceptance | not measured | no matched downstream outcome |
| runner latency | observed but not promotion evidence | machine-local, not paired agent latency |

The frozen supplemental overlap corpus is also preserved: its two duplicate/hash cases each reduce selected bytes by 50% with critical recall 1.0; its distinct-information negative control reduces 0% and preserves recall 1.0. This is evidence for #24 only and is not substituted for the #23 baseline.

## Candidate feature checks

The final relevant suite passed through the required parser-observed path: 30 tests covering the original #23 corpus, overlap extension, structural slices, progressive expansion, task-aware routing, failure-localized refresh, and Wave 2 context/evidence contracts.

## Outliers and limitations

- The #23 runner explicitly treats its reduction as an upper bound because it assumes the agent reads every candidate file.
- No accepted coding task was replayed both with and without vNext, so task-success regression and tool-call savings are unknown rather than zero.
- Estimated tokens are clearly separated from unavailable provider/Codex tokens.
- No provider, hidden index, embeddings, vector database, autonomous retrieval loop, or authority expansion was introduced by children #24–#28.

## Required follow-up before PASS

Capture an owner-approved matched coding-agent replay corpus with observed tool calls, downstream acceptance, and paired latency. Re-run the same tasks at the final candidate revision, retain outliers, and promote only if the #29 criteria are met.
