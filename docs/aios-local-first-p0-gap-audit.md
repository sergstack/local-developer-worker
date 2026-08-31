# AI-OS local-first execution layer — P0 gap audit

**Issue:** [#56](https://github.com/sergstack/local-developer-worker/issues/56)
**Upstream policy:** [sergstack/AI-OS#345](https://github.com/sergstack/AI-OS/issues/345)
**Status:** `P0_COMPLETE_NO_RUNTIME_CHANGE`

This maps AI-OS policy requirements to current LDW mechanisms. It is neither
an AI-OS policy registry nor a promotion decision or production allowlist.

## Decision

LDW already provides bounded context, evidence lineage, deterministic test and
Git facts, privacy-safe telemetry, loopback-only local inference, and Codex
fallback/escalation. It must not duplicate AI-OS semantic policy or promote a
task class.

The first proven implementation gap is loss-aware context compaction. Two later
gaps remain before real local-first promotion can be evaluated: a
caller-supplied offload-policy envelope and a reusable real-task matched-study
export.

## Classification

- `already_sufficient`: current public contract provides the bounded mechanism.
- `partial_gap`: useful mechanics exist but a reusable contract boundary or
  required measurement is missing.
- `material_gap`: no safe general mechanism covers the policy requirement.

## Capability map

| AI-OS #345 requirement | Current LDW evidence | Classification | Smallest safe next step |
| --- | --- | --- | --- |
| Progressive disclosure | `ldw context pack` requires an allowed root and records inclusion/exclusion reasons and relevance. | `already_sufficient` | Preserve direct read → pack. |
| Context expansion | `mode=expand` requires prior package/run ID and an explicit missing-context reason or deterministic trigger; safety checks repeat. | `already_sufficient` | Preserve the current contract. |
| Context compaction / summarization | No `ldw context compact` command or loss-aware preservation contract exists. Packs expand and refresh but cannot compact working state. | `material_gap` | Design a compact-only contract that preserves declared critical fields or returns `partial`/`blocked`. |
| Local semantic offload | `ldw log process` and `ldw ollama advise` provide bounded, loopback-verified candidate inference, structured validation, and no raw-response retention. | `partial_gap` | Reuse these primitives; do not add model transport. |
| Adaptive Codex routing | `ldw codex run` provides abstract profiles, risk floors, exact-session escalation, and explicit verification status. | `partial_gap` | Accept an AI-OS-supplied class/risk/offload disposition; do not hard-code the taxonomy. |
| Deterministic verification | `ldw test parse` is test-status authority; `ldw git facts` is Git-fact authority; context/log flows validate accounting. | `already_sufficient` | Prefer these tools before inference whenever they establish the fact. |
| Evidence provenance | `ldw evidence build` preserves supplied lineage and keeps model groups separate from observed evidence. | `already_sufficient` | Keep future offload results candidate-only. |
| Tool/context telemetry | Generic events capture status, latency, fallback and context reduction; Codex routing captures aggregate profile, token and escalation facts. No per-class local-vs-control study record exists. | `partial_gap` | Add only aggregate study/export fields under existing privacy rules. |
| Local-model allowlist / policy ingestion | Current policies configure capabilities/routes but no neutral input accepts `offload_mode`, `risk_floor`, `verification_kind`, `fallback_policy`, and `policy_revision`. | `material_gap` | Define a bounded input schema; AI-OS remains sole policy owner. |
| Fallback / escalation | Codex supports exact-session escalation and constrained fallback; local paths fail closed but lack a unified offload-route result contract. | `partial_gap` | Specify visible fallback/escalation fields in the future envelope. |
| Matched real-task evaluation | `ollama_advisory_study` analyses aggregates and makes synthetic evidence non-promoting, but is not a reusable real-task runner/export. | `material_gap` | Build opaque-ID aggregate evidence export only; AI-OS decides promotion. |
| Rollback / disable | Codex/Ollama paths are opt-in and policy-gated, but no common local-offload route exists. | `partial_gap` | Require an explicit disable path in future execution. |

## Verified ownership boundary

| Concern | Owner | Evidence |
| --- | --- | --- |
| Task eligibility, risk floor, promotion and authority semantics | AI-OS | [AI-OS #345](https://github.com/sergstack/AI-OS/issues/345) |
| Context, local transport, validation, routing mechanics, fallback, telemetry and execution evidence | LDW | [#56](https://github.com/sergstack/local-developer-worker/issues/56), [tool contracts](tool-contracts.md) |
| Test status and Git state | Existing deterministic LDW tools | [tool contracts](tool-contracts.md) |

LDW must not infer or store an independent AI-OS registry, promote a class from
telemetry, or convert model output into observed evidence or owner authority.

## Evidence boundary

- Context-pack reduction is bytes, not inferred token savings.
- The five-pair terminal-triage pilot is synthetic technical evidence only;
  it cannot authorize real repository work or a production allowlist.
- `ldw ollama advise` is read-only, loopback/runtime verified, and has no
  repository, tool, write, merge, deploy, or acceptance authority.
- Telemetry excludes prompts, paths, source, provider responses, secrets,
  concrete model IDs, and persistent session/thread IDs.

## P1 handoff to Codex

**From:** AI-OS #345 / LDW #56 P0 audit
**To:** Codex implementation
**Task type:** bounded contract and test implementation
**Mode:** strict
**Objective:** implement only a loss-aware context-compaction primitive that
preserves caller-declared critical state without inventing requirements,
authority, acceptance semantics, or evidence.
**Constraints:** no AI-OS registry; no promotion; no new model transport; no
raw prompts, source, responses, secrets or repository-wide semantic ingestion;
existing public commands remain compatible.
**Authority provenance:** AI-OS #345 and LDW #56 are `owner_instruction` for
the boundary and mechanics, not for promotion, merge, deploy, or acceptance.
**Expected output:** versioned `context compact` input/output contract,
deterministic preservation validation, visible `partial`/`blocked` on failure,
focused tests, and isolated rollback.
**Acceptance criteria:** exact/source-referenced declared goal, constraints,
IDs, authority, acceptance, evidence refs, blockers and no-repeat actions;
candidate-only summaries; preserved/compacted/dropped fields and byte
measurements in output; existing context-pack safety remains compatible.
**Risks:** lost decision-bearing state, duplicated AI-OS policy, privacy
regression, or presenting byte reduction as token savings.
**Rollback:** close implementation PR before merge or revert its isolated
commit.
**Merge/gate status:** owner review under canonical AI-OS policy; executor does
not manually merge.

## P0 acceptance trace

| Requirement | Status | Evidence | Limitation |
| --- | --- | --- | --- |
| Map required areas | `passed` | Capability map; tool contracts, routing spec, telemetry docs and source inspected. | No feature is re-executed by this audit. |
| Preserve ownership split | `passed` | Explicit boundary and P1 handoff. | Policy remains upstream in AI-OS. |
| Identify smallest justified work | `passed` | `context compact` is the sole immediate implementation candidate. | Later P2–P4 work is not implemented. |
| Avoid policy/production mutation | `passed` | Documentation-only scope. | No class is promoted. |

## Out of scope

- `context compact` implementation;
- changes to Ollama/Codex execution or telemetry schemas;
- any local-first allowlist, policy registry or promotion decision;
- real provider calls, live matched task runs, merge/deploy automation;
- rewriting historic synthetic evidence.
