# PB4-03 verified Mac-local model evaluation

Summary: The frozen PB4-03 v2 corpus was evaluated once across four exact Mac-local model tags. All 20 calls were valid and fully accounted; no model winner is established from five cases.

Execution status: COMPLETE
Repository: `/Users/sst/prod/Codex Tools-pb4-03`
Worktree: `/Users/sst/prod/Codex Tools-pb4-03`
Branch: `codex/pb4-03-deterministic-accounting`
HEAD: `048fc96c745c2aad25990f77b94cb3bd9daf8735`

## Listener verification

- 11435 listener: `127.0.0.1:11435`
- PID: `21661`
- process: `ollama serve`
- executable: `/Users/sst/.local/libexec/ollama-runtime/ollama`
- physical host: Mac
- tunnel/proxy: false
- verification status: passed
- 11434 known role: SSH listener for the Windows tunnel; sensitive tunnel arguments were not collected

## Previous qwen3.5:9b evidence

- endpoint: `http://127.0.0.1:11434/api/generate`
- physical host: Windows through tunnel
- Mac-local claim: false
- comparison inclusion: excluded from Mac-local comparison
- external internet inference: not observed

## Evaluator contract

- explicit endpoint: required and exactly `http://127.0.0.1:11435/api/generate`
- policy endpoint ignored: yes; policy files are not read
- environment endpoint ignored: yes; no environment override exists
- fallback endpoint: forbidden and not used
- contract version: 2
- prompt hashes: pytest `19700f00f4ee2c3026736a44587b1ab730618995548d95c29ba7550d2f6fa480`; compile-error `47b5060b49c270a893dcdd9ec1d4dae190dbafcb3da828ec0f30bc192542f6d9`; mixed `37d65b92d7ded6cfa57def34f3683d9c9f3cf3c6623ffbae0ba395f013ff45ec`; CLI/build `b6c17c6cdd091073949fdd7e631c463f2d3f4e502e9a7c91e3907b31a5e68ed5`; application/validation `20efec51641de464979dcbd7e9f5afd532277f0c8d8cc5611a60b9b268848b26`
- schema hash: `af24d223030385b25e4e4f3a7e042b3bca7c66e50566a70f24b6d3d2473c8faf`
- validator hash: `419063f91a050cc58d31c8ffa61cdf1ffd2ba79455328aaff01285eb7a4b066d`
- options hash: `4183b81680137ce13e1bba47648e1be483ca77ce5cef9915599553732292fbc8`

## Frozen corpus

- manifest hash before: `51a983b4ed07c70bcfff7a3caadfc711c397ee7b55b8767300f63d0532522f0b`
- manifest hash after: `51a983b4ed07c70bcfff7a3caadfc711c397ee7b55b8767300f63d0532522f0b`
- expected accounting metadata hash before/after: `00c44f860d2828d79c1de162d66f2d0bdd877c9d09709be24f7e59299482a6df`
- case count: 5
- fixture hashes: pytest `c310e6aaeb24a44e373b48016958d46409b8744fbdc00a87902379b1e5afc194`; compile-error `e9402489bb93bfda597598acc3399a5c9d1f4af6705c311d97cca2312ed7e254`; mixed `f566a9e8d171a938ce1543462962cf13f3afa7d496807a103fdb35288d3920fd`; CLI/build `d6b98068b84d06a3b037ea05aa0e009975c08db86b8913a2984bcda7b1e2047f`; application/validation `6f8b0ccae8898779f2c407e06ab2537690430d5f69f3791311ba295d8462ee04`
- unchanged: true
- live evidence SHA-256: `6111ecc804f0da1024a24cc5ecb80db1d0858442e91ddf7cff9025725ff80a5c`

## Model preflight

- qwen3:4b: exact tag present before every call; response identity matched
- gemma3:4b: exact tag present before every call; response identity matched
- ibm/granite4.1:8b: exact tag present before every call; response identity matched
- qwen3:8b: exact tag present before every call; response identity matched

## Execution matrix

- expected runs: 20
- attempted: 20
- valid: 20
- invalid: 0
- infrastructure retries: 0

## Per-model results

| Model | Fully accounted | Accepted | Rejected | Fallback | Returned/schema-valid | Invented/duplicate/omitted candidate IDs | False merges/splits | Catch-all | Needs review | Median/max latency ms | Useful |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| qwen3:4b | 5/5 | 1 | 4 | 4 | 5/5 | 8/4/3 | 0/4 | 0 | 0 | 4403/5445 | 1/5 |
| gemma3:4b | 5/5 | 3 | 2 | 2 | 5/5 | 0/5/0 | 0/2 | 0 | 0 | 5674/8176 | 3/5 |
| ibm/granite4.1:8b | 5/5 | 0 | 5 | 5 | 5/4 | 12/6/14 | 0/5 | 0 | 0 | 8926/28619 | 0/5 |
| qwen3:8b | 5/5 | 5 | 0 | 0 | 5/5 | 0/0/0 | 0/1 | 0 | 0 | 9215/11417 | 4/5 |

All accepted candidates had zero invented, duplicate, or omitted candidate IDs. Every model had 100% fallback coverage and zero unclassified observed events. Rejected-candidate ID counts remain visible and are not treated as accepted evidence.

## Comparison

- safety-qualified models: all four
- highest acceptance: qwen3:8b
- lowest fallback: qwen3:8b
- lowest false merge: all four (zero)
- lowest review burden: all four (zero)
- fastest median: qwen3:4b
- highest operational usefulness: qwen3:8b
- winner: NOT ESTABLISHED
- confidence: insufficient five-case corpus

## Safety

- physical execution host: Mac
- external internet inference observed: false
- raw response stored: false
- endpoint fallback used: false
- model pull performed: false

## PB4-04 gap

- recorded: yes, in `docs/gate_registry.json`
- implementation: not started; production loopback policy unchanged
- next decision: separately evaluate locality attestation and tunnel detection controls

## Acceptance check

| Requirement | Status | Evidence | Risk |
|---|---|---|---|
| Mac-local listener | implemented | local Ollama PID/executable on 11435 | process snapshot is not cryptographic attestation |
| Four exact tags | implemented | per-call `/api/tags` and response identity | tags can change after this run |
| Frozen corpus | implemented | before/after hashes identical | only five cases |
| 20 controlled calls | implemented | 20 valid, zero retry | single observation per pair |
| Accounting safety | implemented | 5/5 per model, accepted ID integrity zero, fallback 100% | rejected models remain operationally weak |
| Semantic comparison | implemented | fixed rubric and safe per-run evidence | winner not established |
| Raw response exclusion | implemented | evidence contains only structured safe fields | retained older diagnostic artifact remains separately preserved |
| Locality-policy gap | implemented as governance record | PB4-04 not_started | production enforcement remains absent by scope |

Files changed: evaluator and reaggregator scripts, focused evaluator tests, safe Mac evidence, fixture validator, governance and acceptance documentation.

Commands run: listener/process checks, exact-tag preflight, evaluator help, focused/full tests, validators, one 20-run matrix, zero-call reaggregation.

Tests observed: code-gate full suite 177 passed via `ldw test parse`.

Assumptions: frozen required pairs and forbidden merges define operational usefulness. Listener process identity establishes physical Mac execution for this run under the supervisor-approved rule.

Missing evidence: human review corrections; a larger corpus sufficient for confident model ranking.

Risks: five cases are too few to establish a winner; Granite produced substantial rejected ID errors; qwen3:8b accepted all cases but false-split the compile-error relation.

Blockers: no blocker to PB4-03 technical owner review; model winner remains deliberately unresolved; routing-mode decision and Git publication approval remain separate.

Commit: not run
Push: not run
PR: not run
PB4-03 owner acceptance readiness: yes for Mac-local evaluation and reconstructed integration
