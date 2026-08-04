# Stage B model posture and supervised activation

Goal: establish the Stage B model posture.

Execution status: `selected_and_supervised_active`; owner selected Option A and the global explicit-only runtime uses `qwen3:8b`.  
Repository: `/Users/sst/prod/Codex Tools`  
Worktree: `/Users/sst/prod/local-developer-worker-model-confirmation`  
Branch: `codex/pb4-model-confirmation`  
HEAD: `1e738256dfbd72fcac4386d8a3c9a0d776f3e6d9`

## Installed runtime — OBSERVED

- entrypoint: `/Users/sst/.local/bin/ldw`
- editable source worktree: `/Users/sst/prod/Codex Tools`
- source branch: `main`
- source commit: `82d2073f78ff2ebb26d8c94a8b0e95831e36e421`
- source dirty: true; one unrelated untracked `tests/stage_b/test_wave_3_adoption.py`
- imported package/CLI/log-process/cluster modules all resolve under that source worktree
- accepted semantic grouping contract: v2 with deterministic accounting and explicit-only routing

The clean model-confirmation branch was fast-forwarded to local `origin/main` at `1e73825`, which contains accepted prerequisite PR #5. The remote ref was not freshly fetched because fetch requires separate approval.

## Current global configuration — OBSERVED

- policy SHA-256: `fa9a57062ce0fc755b4e73b4c72e7fb4f0b760a239861266ca7e92b6417a16b6`
- profile: `balanced`
- configured model: `qwen3:8b`
- endpoint: `http://127.0.0.1:11435/api/generate`
- semantic enabled: true
- semantic log clustering: true
- automatic size/signature routing: disabled; semantic routing is explicit per call
- code artifact: disabled
- automatic edit/commit/merge/deploy: false/false/false/false
- global `/Users/sst/.codex/AGENTS.md` SHA-256: `ec117ba631be0825b2cd465e9a6957ebb6c6c42bfb1bde424ecbf4413861a32f`

## Mac-local runtime — OBSERVED

- listener: `127.0.0.1:11435`, PID 21661 at observation time
- executable: `/Users/sst/.local/libexec/ollama-runtime/ollama serve`
- physical host: Mac; tunnel or proxy observed on 11435: false
- exact `qwen3:8b` tag: present
- exact `gemma3:4b` tag: removed after the selected-model smoke
- Windows tunnel port 11434: excluded and not queried

## Contract and dependency gate — RESOLVED

Contract v2, candidate-only input, deterministic dispositions, reconciliation, full observed fallback, and explicit-per-call routing are present in merged main `82d2073f78ff2ebb26d8c94a8b0e95831e36e421`. A repeated error without `semantic: true` does not invoke the model. The accepted dependency gate is therefore closed.

## Evidence — SOURCE-REPORTED, hash-verified

- Mac evaluation artifact SHA-256: `62423f006f5f9ac7f2b871a9880490a1206157449ec9068471184aa11dc02368`
- corpus SHA-256 observed and recorded: `51a983b4ed07c70bcfff7a3caadfc711c397ee7b55b8767300f63d0532522f0b`
- matrix: 20 expected / 20 attempted / 20 valid / 0 invalid
- all calls used endpoint 11435 and exact requested/reported model identity
- raw provider response stored: false; endpoint fallback: false; model pull: false
- qwen3:8b: accepted 5/5, fallback 0, false splits 1, useful 4/5, median latency 8936 ms
- gemma3:4b: accepted 3/5, fallback 2, false splits 2, useful 3/5, median latency 5631 ms
- qwen3.5:9b included in this comparison: false
- formal winner: `NOT ESTABLISHED`; confidence: insufficient five-case corpus

The accepted Phase 2 evidence separately records one real qwen3:4b response on 11435 followed by full deterministic fallback; artifact SHA-256 `31f2c232fc0a49854edde23f90b7d64b806c666b51849a3a5e15b1398fa3b3bc`.

## Draft operational profiles

- `supervised_quality`: qwen3:8b, provisional recommendation, explicit manual per call, contract v2.
- `supervised_fast`: gemma3:4b, challenger, explicit manual per call, contract v2.
- both: endpoint 11435, temperature 0, think false, model fallback disabled, deterministic fallback available, code artifacts disabled, external network and mutations denied.
- archived file field for both: `blocked_dependency`; neither profile file was applied verbatim. The selected quality model was activated through the balanced explicit-only profile.

## Owner decision — selected

- Option A — selected: qwen3:8b supervised quality model with explicit manual invocation.
- Option B: retain both manual profiles and require an explicit quality/fast selection per call.
- Option C: no activation until a larger confirmation corpus is complete.

```yaml
selected option: A
model: qwen3:8b
decided_by: user
decision_date: 2026-08-04
```

The five-case corpus remains too small to establish a universal model winner. This is the owner's supervised operational selection, not a broader quality claim. The `supervised_fast` file is retained only as historical comparison configuration; its `gemma3:4b` model is no longer installed.

## Activation and runtime smoke

- quality model applied through the global balanced profile: true
- fast profile applied: false
- global default changed: true (`qwen3:8b`)
- automatic routing disabled: true
- deterministic bypass smoke: `PASS` on 2026-08-04; repeated errors without `semantic: true` produced `semantic_attempted=false`
- qwen quality smoke: `PASS` on 2026-08-04; `semantic_attempted=true`, `semantic_accepted=true`, `fallback_used=false`, full accounting true; `ollama ps` confirmed `qwen3:8b` on `127.0.0.1:11435`
- gemma fast smoke: `NOT RUN`
- negative endpoint and invalid-candidate smoke: `NOT RUN` for the target posture

## Model posture

- recommended quality model — RECOMMENDATION: qwen3:8b, provisional
- configured global model — OBSERVED: qwen3:8b
- actually invoked model — OBSERVED: qwen3:8b on the selected-profile smoke
- activated target model — OBSERVED: qwen3:8b under the balanced explicit-only profile
- fast challenger — HISTORICAL: gemma3:4b, removed from the Stage B runtime after selection
- formal winner — NOT ESTABLISHED
- economic winner — NOT MEASURED
- operator time saving, human review corrections, and time to actionable result — NOT MEASURED

## Safety, blockers, and rollback

- raw response stored by retained Mac evidence: false
- external endpoint used: false
- automatic edit/commit/merge/deploy granted: false
- blockers: none for supervised qwen3:8b operation; the small corpus still prevents a universal-winner claim
- rollback: restore `model = "qwen3:4b"` only after reinstalling that removed model, or select another installed loopback model; deterministic Stage A and Codex fallback remain available
- Git actions: local fast-forward only; no fetch, staging, commit, push, PR, merge, or deploy
- next resumable action: collect supervised usefulness marks; automatic routing remains disabled

## Tests and missing evidence

- tests observed: full local suite and focused model-posture/contract checks, with status established through `ldw test parse`
- missing evidence: larger quality corpus, direct usefulness marks, fast-profile post-selection smoke, negative-endpoint and invalid-candidate post-selection smoke
- economic evidence: `NOT MEASURED`

Portfolio acceptance: `selected_and_supervised_active`; owner decision A and qwen3:8b live smoke are complete. Automatic routing remains disabled.
