# Context Efficiency live matched replay — 2026-08-28

## Verdict: STOP

This owner-authorized #37 study used isolated historical worktrees, the same
Codex model/budget/timeout per pair, a deterministic baseline/candidate context
package, and parser-observed pytest verification. Raw prompts, JSONL, tool
arguments, and provider text were never retained.

The frozen five-task corpus was stopped after the third executed pair because
T01 had a required task-success regression: baseline verification passed and
candidate verification failed. Per the v1.1 contract, that is a STOP condition;
the two unrun pairs cannot be used to override it.

| Task | Baseline context / tools / latency | Candidate context / tools / latency | Acceptance |
| --- | --- | --- | --- |
| T04 replay environment contract | 77,088 / 10 / 105,369 ms | 2,276 / 15 / 121,954 ms | pass / pass |
| T05 structural context slicing | 74,451 / 13 / 128,669 ms | 40,956 / 16 / 129,720 ms | pass / pass |
| T01 progressive context expansion | 74,451 / 26 / 262,836 ms | 43,548 / 19 / 252,735 ms | pass / **fail** |

Observed input tokens decreased in every completed pair, but that is not a
substitute for the required tool-call, latency, and task-success acceptance.
T04 and T05 also increased tool calls and latency. Therefore this study does
not demonstrate material Context Efficiency improvement, cannot close #37 or
#22, and must not be compared to or replace the immutable #23 baseline.

## Reproducibility boundary

The historical source/test revisions, temporary policy preflight, and
parser-observed verifier outcomes were recorded during execution. The temporary
worktrees and policy are deliberately not committed. A follow-up may investigate
the T01 regression only as a new owner-authorized study with a new frozen corpus
or revised candidate; it must retain this STOP result as prior evidence.
