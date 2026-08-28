# Context Efficiency live matched replay v2.1 — 2026-08-28

## Verdict: REVISE

This is a new owner-authorized #37 study, not a rewrite of the immutable #23
baseline or the prior STOP evidence. It uses five frozen, real historical
coding regressions in isolated worktrees at environment revision `963e2c1`.
Each matched pair used one Codex run per arm, the same 95,000-byte context
budget, 300-second timeout, model, verifier, and temporary write-capable
policy. The candidate initial context included its immutable verifier test and
any declared frozen fixture/schema through `required_files`; both arms were
rejected if that verifier package changed.

Raw prompts, JSONL, tool arguments, provider output, worktree paths, and test
output were not retained. The table contains only aggregate evidence records.

| Pair | Baseline context / tools / latency | Candidate context / tools / latency | Acceptance |
| --- | --- | --- | --- |
| T01R | 93,343 / 10 / 90,508 ms | 77,744 / 11 / 81,870 ms | pass / pass |
| T02R | 84,899 / 15 / 90,982 ms | 18,866 / 9 / 89,790 ms | pass / pass |
| T03R | 80,101 / 9 / 116,510 ms | 14,068 / 11 / 155,243 ms | pass / pass |
| T04R | 77,979 / 9 / 218,410 ms | 11,946 / 16 / 254,786 ms | pass / pass |
| T05R | 87,176 / 8 / 91,480 ms | 51,215 / 8 / 96,125 ms | pass / pass |

The v1.1 observed-evidence analyzer used opaque evidence and verifier IDs,
baseline revision `eeba6e7`, candidate revision `963e2c1`, and the
owner-approved thresholds below.

| Required metric | Median candidate delta | Threshold | Result |
| --- | ---: | ---: | --- |
| Context bytes | -77.7783% | <= -15% | met |
| Tool calls | +10.0000% | <= -10% | not met |
| Paired latency | +5.0776% | <= -10% | not met |
| Task-success regression | none (5/5 accepted) | none permitted | met |

The strict result is therefore `REVISE`: context reduction is reproducible on
this corpus and required acceptance context was preserved, but there is no
simultaneous material reduction in tool calls and latency. This result cannot
close #37 or #22.

## Outliers and limitations

- T03R and T04R had materially higher candidate latency (+33.2444% and
  +16.6549%) and tool calls (+22.2222% and +77.7778%).
- T01R reduced bytes and latency but increased tool calls by 10.0000%.
- T02R is the only pair meeting both context and tool-call reductions; its
  latency reduction was 1.3101%, below the threshold.
- Each task has one matched run per arm. This is observed coding-agent replay
  evidence, not a claim of general production benefit or token savings.
- The earlier historical-corpus attempt remains a separate STOP record. Its
  T01 failure was traced to a missing immutable verifier dependency and is not
  relabeled or replaced by this v2.1 result.
