# Candidate Lesson Contract v1

`ldw learn validate-candidate` validates one caller-supplied candidate lesson.
It is a boundary after deterministic Rework Miner P0, not a global-log reader,
an LLM runner, or a promotion mechanism.

## Input boundary

The caller must first sanitize any source material.  The validator accepts only
short normalised text fields, opaque IDs, and an allowlist of opaque evidence
references.  It never accepts session files, prompts, commands, tool payloads,
paths, URLs, credentials, provider output, or a transcript.  Sanitization must
remove names, IDs, paths, secrets and secret-like values before the payload is
created.  The validator rejects control characters, unbounded text, duplicate
references and references not in the caller's allowlist.

## Contract

```json
{
  "contract_version": "1.0.0",
  "allowed_evidence_refs": ["EV_001"],
  "candidate": {
    "candidate_id": "CANDIDATE_001",
    "trigger": "repeated_tool_call",
    "observed_problem": "Short sanitised statement.",
    "human_correction": "Short sanitised correction.",
    "rework_class": "execution",
    "generalizable_rule": "Candidate rule, not an instruction to apply.",
    "scope": "Bounded affected surface.",
    "counterexamples": ["When the rule does not apply."],
    "evidence_refs": ["EV_001"],
    "occurrence_count": 3,
    "candidate_destination": "execution_handling",
    "confidence": "low"
  }
}
```

`rework_class` is one of `scope`, `evidence`, `acceptance`, `role_routing`,
`execution`, `observability`, or `workspace_hygiene`.  `candidate_destination`
is one of `regression`, `skill`, `ai_os_rule`, `execution_handling`, or
`reject`.  Confidence is qualitative: `low`, `medium`, or `high`.

## Output and gates

A successful result establishes only schema validity and opaque evidence
lineage.  Its status is always `candidate_only`, with `reuse_status` set to
`judge_required`.  It does not establish causality, task benefit, authority,
or permission to change a skill, policy, route, or product behavior.

Before any reuse, an LLM Judge must evaluate the bounded candidate against its
sanitized evidence.  Any promotion then requires the applicable human or
AI-OS owner decision.  If sanitization, evidence lineage, or a required Judge
result is unavailable, reject or retain the candidate as unpromoted.

## Rollback

No source policy, skill, route, session, or telemetry record is mutated.  To
stop using the contract, do not call it; existing candidate outputs remain
non-promoting historical evidence.
