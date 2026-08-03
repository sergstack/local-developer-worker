# Release gates

This file is generated from `docs/gate_registry.json`. Do not edit it by hand.
Run `python scripts/generate_release_gates.py --check` to detect drift.

`architectural` means the worker enforces the guarantee when the command is invoked;
`advisory` means invocation itself is governed by the operating agreement.

| ID | Public guarantee | Exact evidence test IDs | Enforcement mechanism | Classification |
|---|---|---|---|---|
| SA-01 | Every public CLI command emits a schema-valid ToolResult. | `tests/integration/test_stage_a_safety_matrix.py::test_gate_schema_valid_output_for_all_public_commands[doctor]`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_schema_valid_output_for_all_public_commands[log-parse]`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_schema_valid_output_for_all_public_commands[test-parse]`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_schema_valid_output_for_all_public_commands[git-facts]`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_schema_valid_output_for_all_public_commands[files-inventory]`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_schema_valid_output_for_all_public_commands[evidence-build]`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_schema_valid_output_for_all_public_commands[context-pack]`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_schema_valid_output_for_all_public_commands[report-summarize]`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_schema_valid_output_for_all_public_commands[benchmark-run]`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_schema_valid_output_for_all_public_commands[telemetry-summary]`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_schema_valid_output_for_all_public_commands[portfolio-verify]`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_schema_valid_output_for_all_public_commands[portfolio-status]` | The CLI validates every handler result before canonical serialization and replaces invalid envelopes with an explicit internal-error result. | architectural |
| SA-02 | log parse accounts for every input line; unmatched lines become unknown_event and never disappear. | `tests/integration/test_stage_a_safety_matrix.py::test_gate_log_parse_accounts_for_every_input_line_without_silent_loss` | The parser emits one event inside the loop over each input line and reports totals for every parse state. | architectural |
| SA-03 | test parse maps killed or incomplete runs to non-passed states and never claims passed without observed completed evidence. | `tests/integration/test_stage_a_safety_matrix.py::test_gate_test_parse_marks_exit_137_with_truncated_output_incomplete`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_test_parse_cannot_claim_passed_without_observed_completed_pass[zero-exit-no-result]`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_test_parse_cannot_claim_passed_without_observed_completed_pass[missing-exit]`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_test_parse_cannot_claim_passed_without_observed_completed_pass[command-unobserved]`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_test_parse_cannot_claim_passed_without_observed_completed_pass[interrupted]` | Interrupted-run checks precede pass classification; pass requires an observed command, exit code zero, and observed passing test records. | architectural |
| SA-04 | report summarize makes no test claim when observed_test_results is absent. | `tests/integration/test_stage_a_safety_matrix.py::test_gate_report_without_observed_test_results_makes_no_test_claim`<br>`tests/integration/test_stage_a_safety_matrix.py::test_gate_report_summarize_emits_only_evidence_backed_lists` | The summarizer derives tests_observed only from the evidence package and defaults to an empty list. | architectural |
| SA-05 | .env and private-key content expose neither content nor hashes. | `tests/security/test_inventory.py::test_inventory_blocks_env_file`<br>`tests/security/test_inventory_hardening.py::test_inventory_blocks_private_key_content_without_sensitive_name` | Sensitive path matching prevents reads and content scanning blocks detected key material before hashes are emitted. | architectural |
| SA-06 | Symlinks resolving outside the repository root are blocked and unreadable. | `tests/security/test_inventory_hardening.py::test_inventory_marks_symlink_escape` | Resolved-path containment is checked before stat or read operations. | architectural |
| SA-07 | Identical CLI input produces byte-identical stdout and stderr. | `tests/integration/test_stage_a_safety_matrix.py::test_gate_cli_output_is_byte_identical_for_identical_input` | Stable hashes, deterministic run IDs, and canonical sorted JSON remove output variation. | architectural |
| SA-08 | on_timeout fallback is separately reachable and observable. | `tests/integration/test_timeout_and_allowlist.py::test_zero_timeout_returns_non_success_with_fallback` | The CLI stops before dispatch on a non-positive timeout and emits the configured fallback. | architectural |
| SA-09 | on_invalid_schema fallback is separately reachable and observable. | `tests/integration/test_stage_a_safety_matrix.py::test_gate_invalid_schema_fallback_is_reachable_and_observable` | Post-dispatch schema validation replaces invalid handler output with the configured fallback. | architectural |
| SA-10 | on_policy_violation fallback is separately reachable and observable. | `tests/integration/test_policy.py::test_disabled_capability_returns_policy_blocked` | Capability checks precede dispatch and emit policy_blocked with the configured fallback. | architectural |
| SA-11 | on_internal_error fallback is separately reachable and observable. | `tests/integration/test_stage_a_safety_matrix.py::test_gate_internal_error_fallback_is_reachable_and_observable` | The CLI boundary catches unexpected handler exceptions and emits the configured fallback. | architectural |
| SA-12 | Repository roots outside allowed_repository_roots are denied. | `tests/integration/test_timeout_and_allowlist.py::test_cli_blocks_repository_outside_default_allowlist` | Root allowlist validation runs before Git or inventory dispatch. | architectural |
| SA-13 | git facts can invoke only its closed read-only Git command set. | `tests/security/test_stage_a_boundaries.py::test_gate_git_facts_can_only_reach_read_only_git_subcommands` | The collector has a fixed internal call sequence and exposes no caller-controlled Git arguments. | architectural |
| SA-14 | The default policy grants no network, edit, commit, merge, deploy, or semantic authority. | `tests/security/test_stage_a_boundaries.py::test_gate_default_policy_denies_network_mutation_and_deployment` | The shipped policy denies these capabilities and the CLI enforces declared capabilities before dispatch. | architectural |
| SA-15 | Reports do not diagnose root cause or choose architecture beyond observed evidence. | `tests/integration/test_stage_a_safety_matrix.py::test_gate_report_summarize_emits_only_evidence_backed_lists` | The renderer has a closed facts-only mapping sourced from the evidence package. | architectural |
| SA-16 | The absence of technical enforcement requiring Codex to call ldw test parse is publicly disclosed. | `tests/security/test_authority_boundary.py::test_authority_boundary_discloses_advisory_test_parse_enforcement` | Prompt and operating agreement only; no hook, shell wrapper, or runner interception exists. | advisory |

The economic benchmark is informational only. Context-reduction figures are not a Stage A promotion gate and cannot be used as an acceptance blocker.

## Stage A to B action items

| ID | Action | Source | Initial status | Owner action |
|---|---|---|---|---|
| AI-01 | Personal telemetry on real sessions | v3 W1 | not_started | Run at least 10 real CLI calls and verify the privacy-safe summary. |
| AI-02 | Choose SA-16 enforcement posture | v3 W2 | not_started | Keep SA-16 advisory and verify that no wrapper or interception mechanism is installed. |
| AI-03 | Define the Stage B entry gate | v3 W3 | not_started | Review and approve the planning document before any Stage B code or policy change. |
| AI-04 | Reconcile project terminology with personal economics | v3 W4 | not_started | Change PROJECT_DESCRIPTION.md only if market or team framing contradicts the operator-focused criterion. |

## AI-02 decision table

Selected option: `a`.

| Option | Posture | Benefit | Tradeoff |
|---|---|---|---|
| a | Keep advisory | Preserves normal pytest behavior and requires no new mechanism. | Relies on prompt and operating instructions; Codex can still bypass ldw test parse. |
| b | Session shell wrapper | Physically routes pytest invocations through ldw test parse in the configured session. | Rejected: changes ordinary pytest behavior in the user's terminal and may affect workflows outside the Worker. |
| c | Passive reminder | Makes the expected workflow visible through doctor or a system message without intercepting commands. | Improves discoverability but remains non-blocking and therefore advisory. |
