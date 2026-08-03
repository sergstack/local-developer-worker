# Stage B Phase 2 rollback

## Disable semantic clustering

Set either `[semantic].enabled = false` or `[automatic].semantic_log_clustering = false` in the active policy. The shipped `policy.toml` already keeps both values `false`. Keep `[semantic].code_artifact = "disabled"` in every policy.

With `[semantic].enabled = false`, `ldw log cluster` returns `policy_blocked` with `semantic_disabled` before dispatch. With only `[automatic].semantic_log_clustering = false`, it returns `policy_blocked` with `capability_disabled`. Neither path calls the model or grants edit, commit, merge, deploy, or external-network authority.

## Existing evidence

Previously generated `semantic_candidates` remain valid immutable `model-derived` candidate evidence. Disabling the runtime does not relabel, delete, or mutate historical packages. Observed files, commands, tests, and log events remain separate from semantic candidates.

## Recovery

Re-enable only after the Stage A and Stage B gates pass and a supervised loopback call is authorized. The active policy must name the model and loopback endpoint; endpoint validation continues through `guarded_inference_call`.
