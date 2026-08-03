# Wave 2 baseline

Observed from canonical commit `1e738256dfbd72fcac4386d8a3c9a0d776f3e6d9` before Wave 2 implementation changes.

```yaml
context_pack:
  public_cli: "ldw context pack"
  input_schema: "implicit Python dictionary; no public input schema"
  output_schema: "schemas/context_package.schema.json"
  repository_root_required: false
  policy_checks: "context_packer capability only; no allowed-root check"
  sensitive_path_rules: "only caller-supplied potentially_sensitive=true"
  symlink_escape_protection: false
  included_files_output: "audit mode only; path and reasons"
  excluded_files_output: "audit mode only; path and reason"
  run_id: "deterministic ToolResult run_id from tool and input manifest"
  source_lineage: "selection reasons only; no evidence_source or relevance_status"
  expansion_supported: false
  deterministic: true
  current_tests:
    - "unit selection reasons and duplicate handling"
    - "direct import and pytest-layout matching"
    - "sensitive flag exclusion"
    - "one Stage A end-to-end assertion"
  known_gaps:
    - "no explicit repository root"
    - "no path, symlink, binary, ignored, or generated safety enforcement"
    - "context mode hides considered exclusions"
    - "no bounded expansion"
    - "no byte-volume or low-benefit status"
    - "public schema requires only included_files, excluded_candidates, and budget"

evidence_build:
  public_cli: "ldw evidence build"
  input_schema: "implicit Python dictionary; no public input schema"
  output_schema: "schemas/evidence_package.schema.json"
  repository_root_required: false
  policy_checks: "no dedicated capability or allowed-root check"
  sensitive_path_rules: "none beyond supplied inventory metadata"
  symlink_escape_protection: false
  included_files_output: "legacy file_inventory passthrough"
  excluded_files_output: "legacy file_inventory passthrough"
  run_id: "deterministic ToolResult run_id from tool and input manifest"
  source_lineage: "log event hash and line range validation only"
  expansion_supported: false
  deterministic: true
  current_tests:
    - "invalid log source-reference rejection"
    - "duplicate event ID rejection"
    - "facts-only end-to-end preservation of incomplete test status"
  known_gaps:
    - "no explicit repository root"
    - "no per-item source_tool, source_run_id, source_type, path/test/git identifiers, or origin contract"
    - "no context package linkage"
    - "no explicit resume or next bounded action state"
    - "legacy fields can contain unsupported claims without item-level provenance"
    - "public schema requires only task, content_hash, and missing_evidence"
```

Public envelope schema version before Wave 2 is `1.0.0`. Context and evidence payloads have no internal contract-version field, so any accepted extension requires an explicit package contract version and a migration note while preserving legacy keys.
