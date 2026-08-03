# Release gates

Stage A acceptance requires every public guarantee below to have executable evidence.
A test marked `xfail` is evidence of an open defect, not evidence that the guarantee
holds. `Architectural` means the worker enforces the guarantee whenever the relevant
`ldw` command is invoked. It does not mean that Codex is forced to invoke the worker.

| ID | Public guarantee | Evidence test ID | Enforcement mechanism | Classification |
|---|---|---|---|---|
| SA-01 | All nine CLI commands emit a schema-valid `ToolResult` | `test_gate_schema_valid_output_for_all_nine_commands` (nine parameter cases) | The CLI validates the handler result before canonical JSON serialization and replaces an invalid envelope with an error result. | architectural |
| SA-02 | `log parse` accounts for every input line; unmatched lines become `unknown_event` and are never silently dropped | `test_gate_log_parse_accounts_for_every_input_line_without_silent_loss` | The parser creates exactly one event inside the loop over every input line and emits state totals that must equal the input-line count. | architectural |
| SA-03 | `test parse` maps exit 137 or a truncated final result to `incomplete`, never `passed` | `test_gate_test_parse_marks_exit_137_with_truncated_output_incomplete`; `test_gate_test_parse_cannot_claim_passed_without_observed_completed_pass` | Interrupted-run checks precede pass classification; pass requires an observed command, exit code 0, and observed passing test records. | architectural |
| SA-04 | `report summarize` makes no test claim when `observed_test_results` is absent from the evidence package | `test_gate_report_without_observed_test_results_makes_no_test_claim`; `test_gate_report_summarize_emits_only_evidence_backed_lists` | The summarizer derives `tests_observed` only from `evidence_package.observed_test_results`, defaulting to an empty list. | architectural |
| SA-05 | `.env` and private-key content expose neither content nor hashes | `test_inventory_blocks_env_file`; `test_inventory_blocks_private_key_content_without_sensitive_name` | Sensitive path matching prevents reads; content scanning marks detected key material blocked before any hash or content is emitted. | architectural |
| SA-06 | Symlinks resolving outside the repository root are blocked and unreadable | `test_inventory_marks_symlink_escape` | Resolved-path containment is checked before stat/read, and escaped symlinks receive `blocked=symlink_escape`. | architectural |
| SA-07 | Identical CLI input produces byte-identical stdout and stderr | `test_gate_cli_output_is_byte_identical_for_identical_input` | Stable hashes/IDs and canonical sorted JSON serialization remove per-run variation, including `run_id`. | architectural |
| SA-08 | `on_timeout` fallback is separately reachable and observable | `test_zero_timeout_returns_non_success_with_fallback` | The CLI stops before dispatch when the configured timeout is non-positive and returns the configured fallback with a non-success exit. | architectural |
| SA-09 | `on_invalid_schema` fallback is separately reachable and observable | `test_gate_invalid_schema_fallback_is_reachable_and_observable` | Post-dispatch schema validation replaces invalid handler output with `invalid_output_schema` and the configured fallback. | architectural |
| SA-10 | `on_policy_violation` fallback is separately reachable and observable | `test_disabled_capability_returns_policy_blocked` | Capability checks run before dispatch and return `policy_blocked` plus the configured fallback. | architectural |
| SA-11 | `on_internal_error` fallback is separately reachable and observable | `test_gate_internal_error_fallback_is_reachable_and_observable` | The CLI boundary catches unexpected handler exceptions and emits the configured fallback in a non-success result. | architectural |
| SA-12 | Repository roots outside `allowed_repository_roots` are denied | `test_cli_blocks_repository_outside_default_allowlist` | Root allowlist validation runs before `git facts` or `files inventory` dispatch. | architectural |
| SA-13 | `git facts` invokes only its closed read-only Git command set | `test_gate_git_facts_can_only_reach_read_only_git_subcommands` | The collector has a fixed internal call sequence and exposes no caller-controlled Git arguments. | architectural |
| SA-14 | The default policy grants no network, edit, commit, merge, deploy, or semantic authority | `test_gate_default_policy_denies_network_mutation_and_deployment` | The shipped default policy denies these capabilities and the CLI checks declared capabilities before dispatch. | architectural within the worker under the default policy |
| SA-15 | Reports do not diagnose root cause or choose architecture beyond observed evidence | `test_gate_report_summarize_emits_only_evidence_backed_lists` | The report renderer has a closed facts-only output mapping sourced from the evidence package. | architectural |
| SA-16 | The absence of technical enforcement requiring Codex to call `ldw test parse` is publicly disclosed | `test_authority_boundary_discloses_advisory_test_parse_enforcement` | Prompt and operating agreement only; no hook, shell wrapper, or runner interception exists. | advisory |

The economic benchmark is informational only. Context-reduction figures are not a
Stage A promotion gate and cannot be used as an acceptance blocker.
