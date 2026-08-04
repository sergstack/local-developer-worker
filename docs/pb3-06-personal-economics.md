# PB3-06 — Personal economics from observed telemetry

Status: retrospective report complete; forward instrumentation option (a) selected by owner on 2026-08-04  
Observation window: 2026-08-03 through 2026-08-04  
Evidence boundary: privacy-safe `.repo_index/ldw_sessions/*.jsonl` fields only

## Technical summary

The journals prove that Local Developer Worker was used, what byte volumes passed through each command, how long commands took, and when deterministic fallback was reported. They do **not** prove saved Codex tokens, saved operator time, fewer rereads, or fewer manual interventions because no without-Worker baseline or downstream Codex-consumption record was captured.

- **OBSERVED:** 187 valid journal records across six files and four worktrees; a fifth known worktree had no journal. Invalid records: 0.
- **OBSERVED:** 1,094,730 input bytes and 6,311,234 output bytes passed through Worker commands. The output includes JSON envelopes and expanded evidence, so the difference is not token savings.
- **OBSERVED:** `test parse` was the most-used command (59 records), followed by `log process` (43), `doctor` (19), and `portfolio verify` (17). This measures adoption, not value.
- **OBSERVED:** `log cluster` reported fallback on 6 of 7 journal records (85.71%). Its command latency was 5,921 ms median and 15,532 ms maximum. This is operational evidence of high fallback cost, not an economic-savings percentage.
- **OBSERVED:** only one `context pack/context` record contained `context_reduction`; its value was 0.0217 (2.17%). One observation cannot establish an economic result.
- **NOT MEASURED:** the retrospective economic effect. The present evidence cannot support a claim that Worker saved time or Codex tokens.

The final retrospective verdict is therefore: **Worker usage and operational behavior are measured; personal economic savings are not measured.** PB3-06 closes the historical question with that bounded conclusion rather than substituting a proxy for a missing baseline.

## Evidence inventory covers every known worktree

Each valid JSONL line is counted as an observed journal record. Dates come from partition filenames because timestamps are intentionally absent from `SAFE_FIELDS`.

| Worktree | Journal partitions | OBSERVED records | OBSERVED tool distribution |
|---|---:|---:|---|
| `/Users/sst/prod/Codex Tools` | 2026-08-03, 2026-08-04 | 139 | benchmark run 1; context pack/context 1; doctor 14; evidence build 1; files inventory 3; git facts 2; log cluster 1; log parse 5; log process 40; portfolio status 6; portfolio verify 15; report summarize 1; telemetry summary 6; test parse 43 |
| `/Users/sst/prod/Codex Tools-pb4-03` | 2026-08-03, 2026-08-04 | 19 | doctor 4; log parse 1; log process 3; test parse 11 |
| `/Users/sst/prod/local-developer-worker-wave2` | 2026-08-04 | 19 | context pack/context 3; evidence build 2; files inventory 3; git facts 1; log parse 1; portfolio status 1; portfolio verify 2; report summarize 1; test parse 5 |
| `/Users/sst/prod/local-developer-worker-wave3` | 2026-08-03 | 10 | doctor 1; log cluster 6; log parse 3 |
| `/Users/sst/prod/local-developer-worker-model-confirmation` | none | 0 | no journal found |
| **Total** | **6 files** | **187** | **14 command labels** |

No additional worktree was present in `git worktree list`. Wave 3 is the only worktree with a six-record real `log cluster` adoption set. Within those six records, five were `partial` and one was `policy_blocked`; the five non-blocked records all reported fallback. `SAFE_FIELDS` has no model-transport flag, so the journal alone cannot independently prove how many requests reached the provider.

## Observed proxy metrics do not establish savings

All figures below are **OBSERVED** from the 187 valid journal lines at the stated snapshot cutoff. `Input − output` is shown only as byte-flow accounting. It is not a token or context-saving metric because command outputs include protocol envelopes and may expand structured evidence.

| Tool | Calls | Input bytes | Output bytes | Input − output | Fallback | Median latency, ms | Max latency, ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| benchmark run | 1 | 13 | 395 | -382 | 0/1 | 3 | 3 |
| context pack/context | 4 | 943 | 3,829 | -2,886 | 2/4 | 1 | 3 |
| doctor | 19 | 27 | 14,026 | -13,999 | 0/19 | 2 | 4 |
| evidence build | 3 | 576 | 2,511 | -1,935 | 1/3 | 1 | 3 |
| files inventory | 6 | 260 | 1,561,236 | -1,560,976 | 1/6 | 195.5 | 246 |
| git facts | 3 | 122 | 3,432 | -3,310 | 0/3 | 46 | 48 |
| log cluster | 7 | 114,210 | 112,716 | 1,494 | 6/7 | 5,921 | 15,532 |
| log parse | 10 | 9,287 | 26,024 | -16,737 | 0/10 | 1.5 | 3 |
| log process | 43 | 330,936 | 2,535,078 | -2,204,142 | 1/43 | 2 | 5,376 |
| portfolio status | 7 | 21 | 188,777 | -188,756 | 0/7 | 18 | 35 |
| portfolio verify | 17 | 107 | 446,656 | -446,549 | 0/17 | 9,921 | 11,320 |
| report summarize | 2 | 503 | 1,403 | -900 | 0/2 | 2 | 3 |
| telemetry summary | 6 | 17 | 3,543 | -3,526 | 0/6 | 3 | 3 |
| test parse | 59 | 637,708 | 1,411,608 | -773,900 | 0/59 | 2 | 3 |
| **Total** | **187** | **1,094,730** | **6,311,234** | **-5,216,504** | **11/187** | — | — |

The all-tool fallback ratio is 11/187 (5.88%), but that aggregate hides the operationally important concentration: `log cluster` is 6/7 (85.71%), while `log process` is 1/43 (2.33%). Neither rate measures economic benefit.

`log cluster` is the only journal label that unambiguously identifies the model-capable command. Its latency is reported separately above. `log process` mixes deterministic and potentially semantic execution; because `SAFE_FIELDS` lacks `semantic_attempted` and model-transport fields, its 2 ms median and 5,376 ms maximum cannot be split retrospectively into deterministic and model subsets.

## Byte-flow proxy is not Codex context avoided

The journals directly observe Worker input and output sizes. They do not record whether raw input, Worker output, both, or neither were subsequently sent to Codex. Therefore:

- **OBSERVED proxy:** Worker received 1,094,730 bytes and emitted 6,311,234 bytes.
- **OBSERVED proxy:** the aggregate `input_bytes − output_bytes` is -5,216,504 bytes.
- **NOT MEASURED:** the number of raw bytes actually kept out of Codex context.
- **NOT MEASURED:** net Codex token savings.

The only stored context-reduction value is 0.0217 on one `context pack/context` record. It describes that recorded candidate-size comparison only. It is not promoted to a portfolio average, a token estimate, or a personal-economics conclusion.

Synthetic Stage A and Wave 2 context-reduction benchmarks are excluded from this report. Their `INFORMATIONAL_ONLY` results are not mixed with real-session telemetry.

## Required measurement gaps remain NOT MEASURED

| Question from v3 §0 / Wave 3 | Status | What the present journals establish |
|---|---|---|
| How much raw text did not go to Codex | **OBSERVED proxy / NOT MEASURED actual delivery** | Worker input/output byte flow is observed; downstream Codex consumption is not recorded. |
| Codex tokens saved with versus without Worker | **NOT MEASURED** | No without-Worker baseline and no Codex token counter. |
| Time to restore a task after interruption | **NOT MEASURED** | No interruption/resumption timestamps or baseline. |
| Files reread by Codex | **NOT MEASURED** | File-read events and session-scoped rereads are not instrumented. |
| Manual operator messages required | **NOT MEASURED** | Operator-message events are absent from `SAFE_FIELDS`. |
| Corrections of unsupported execution claims | **NOT MEASURED** | Such corrections were discussed manually, but the restricted telemetry has no event or denominator for them. Conversation recollection is not substituted for a journal count. |
| Time spent producing the final report | **NOT MEASURED** | No start/end timing was captured for report production. |

Invocation frequency is an adoption proxy only. Fallback frequency is an operational-quality signal only. Neither is treated as a value or savings proxy.

## Method and robustness boundary

The aggregation validates exact `SAFE_FIELDS`, then groups every valid journal line by worktree and `tool`. Sums use `input_bytes` and `output_bytes`; fallback rate is `fallback_used=true / journal records`; latency is the median and maximum of `latency_ms`. All arithmetic was performed by Python over the six journal files.

`run_id` is deterministic and is not a unique invocation identifier: 187 journal records contain 137 distinct values. Deduplicating by `run_id` would silently discard genuine repeated calls. The primary report therefore counts journal lines.

As a sensitivity boundary, six records belong to three exact event-value groups that occur in more than one worktree. The current fields cannot distinguish copied journal evidence from independently repeated identical calls. Under the strongest overlap assumption, the record count would be 181 rather than 187; for `log cluster`, it would be 6 rather than 7, fallback 5/6 (83.33%), median latency 4,513 ms, and maximum 15,532 ms. This sensitivity does not change the verdict: usage and high clustering fallback are observed, while savings remain unmeasured.

No trend chart is included because the evidence covers only two date partitions and has no event timestamps. Exact audit tables communicate the supported result without implying a time trend.

Journal snapshot cutoffs used for this report are explicit because the files are append-only. Each hash covers exactly the stated number of leading lines, including their line endings; later appends do not change this analytical cutoff.

| Journal | Leading lines | Prefix SHA-256 |
|---|---:|---|
| `Codex Tools/.repo_index/ldw_sessions/2026-08-03.jsonl` | 51 | `ddd7864305b2fb85cd6e325833bee39ef21b4817842b19ee1bd7237c050b0657` |
| `Codex Tools/.repo_index/ldw_sessions/2026-08-04.jsonl` | 88 | `25097a1488c267e412fb508441017b650ff15f19c6c46ae2bd61d7361cb8738a` |
| `Codex Tools-pb4-03/.repo_index/ldw_sessions/2026-08-03.jsonl` | 9 | `72b7593614d33232ad9a0f12246282211da2358bddd40f63ec98c4a0de02bd71` |
| `Codex Tools-pb4-03/.repo_index/ldw_sessions/2026-08-04.jsonl` | 10 | `9693ca6228d2e694bfc0705fffe4e56deb1d006d603ded3b633445cb6aabf226` |
| `local-developer-worker-wave2/.repo_index/ldw_sessions/2026-08-04.jsonl` | 19 | `99fa14149426b165612c355bbb481695bfedf759afd856e64e346a2cf8324e41` |
| `local-developer-worker-wave3/.repo_index/ldw_sessions/2026-08-03.jsonl` | 10 | `4aa6a11ef319314bdc0f3881b3ca9361d7a5d8717509bcb1a8901e31e03b5c51` |

## Forward instrumentation options require an owner decision

No option is selected or implemented by this report.

### Option (a): manual usefulness label

After a session, the operator records `helped: true`, `helped: false`, or `helped: unclear`.

- Lowest implementation complexity and the clearest direct personal-value signal.
- Requires consistent manual input and remains subjective.

### Option (b): automatic same-session reread proxy

Record a repeated read of the same file within one session as a signal that the first context package may have been insufficient.

- Removes operator effort and creates a repeatable behavioral proxy.
- A reread may be intentional, so this cannot be labeled direct savings without validation.
- Requires a privacy-safe session/file identity design before implementation.

### Option (c): no additional instrumentation

Keep economics at the present level: correctness, usage, latency, and fallback behavior only.

- No new collection or operator burden.
- Personal time and token savings remain permanently unmeasured.

**Owner action:** choose (a), (b), or (c) based on which future decision the measurement must support. If direct personal usefulness is the target, only (a) measures it directly; if zero-touch operational monitoring is the target, (b) supplies a rough proxy; if neither justifies the collection cost, (c) is internally consistent. This report does not choose on the owner's behalf.

## Closure

PB3-06-1 (journal inventory), PB3-06-2 (observed proxy aggregation), PB3-06-3 (measurement-gap disclosure), and PB3-06-5 (final report) are complete for the captured 2026-08-03 through 2026-08-04 evidence. PB3-06-4 was subsequently resolved by the owner in favor of option (a). No retrospective savings claim is supportable from the current telemetry, and no further retrospective calculation can repair the missing baseline.

Owner decision addendum, 2026-08-04: option (a), the manual `helped|not_helped|unclear` usefulness mark, was selected for forward measurement. This later decision does not change the retrospective `NOT MEASURED` verdict above.
