"""Compile bounded LDW evidence references into deterministic review semantics.

This P0 module does not read repositories, invoke models, render artifacts, or
promote a finding.  The caller retains the authoritative LDW evidence package;
this module accepts only its compact provenance references and declared review
scope.
"""
from __future__ import annotations

from html import escape as html_escape
from typing import Any

from .contracts import canonical_json, result, sha256, stable_hash


ROOT = {"contract_version", "objective", "scope", "git_facts", "evidence", "required_checks"}
P1_ROOT = ROOT | {"contract_comparison"}
SCOPE = {"scope_id", "change_size", "changed_components", "declared_boundaries", "contract_change"}
COMPONENT = {"component_id", "kind"}
GIT_FACTS = {"source_tool", "source_run_id", "working_tree_clean", "changed_component_ids"}
EVIDENCE = {
    "source_tool", "source_run_id", "content_hash", "lineage_complete",
    "observed_evidence_refs", "candidate_evidence_refs", "missing_evidence_ids", "unknown_ids",
}
CHECK = {"check_id", "check_type", "status", "source_tool", "evidence_refs"}

COMPONENT_KINDS = {"source", "test", "contract", "configuration", "documentation"}
CHANGE_SIZES = {"local", "bounded", "cross_boundary"}
CHECK_TYPES = {"test", "schema", "git", "manual"}
CHECK_STATUSES = {"passed", "failed", "not_run", "unknown"}
CHECK_SOURCES = {"test_result_parser", "git_facts_collector", "evidence_package_builder", "none"}
PROFILES = {"local", "contract_change", "cross_boundary", "evidence_risk"}
RENDER_ROOT = {"contract_version", "format", "review_package"}
P0_PACKAGE_FIELDS = {
    "contract_version", "review_package_id", "objective", "diagnosis", "review_profile", "affected_invariants",
    "affected_boundaries", "required_checks", "findings", "unknowns", "evidence_refs", "derived_view_plan",
    "authority", "evidence_export",
}
P1_PACKAGE_FIELDS = P0_PACKAGE_FIELDS | {"evidence_ledger", "contract_delta"}


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 64 or not all(
        character.isascii() and (character.isupper() or character.isdigit() or character in "_-")
        for character in value
    ):
        raise ValueError(f"invalid_{label}")
    return value


def _source_run_id(value: Any, label: str, *, allow_canonical: bool) -> str:
    if (
        allow_canonical
        and isinstance(value, str)
        and len(value) == 20
        and value.startswith("RUN-")
        and all(character in "0123456789abcdef" for character in value[4:])
    ):
        return value
    return _identifier(value, label)


def _safe_text(value: Any, label: str, *, limit: int) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(character) < 32 for character in value):
        raise ValueError(f"invalid_{label}")
    return value


def _hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"invalid_{label}")
    return value


def _version_label(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 64 or not all(
        character.isascii() and (character.isalnum() or character in "._-") for character in value
    ):
        raise ValueError(f"invalid_{label}")
    return value


def _identifiers(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"invalid_{label}")
    checked = [_identifier(item, label) for item in value]
    if len(checked) != len(set(checked)):
        raise ValueError(f"duplicate_{label}")
    return checked


def _validate_scope(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != SCOPE:
        raise ValueError("invalid_review_scope")
    _identifier(value["scope_id"], "scope_id")
    if value["change_size"] not in CHANGE_SIZES or not isinstance(value["contract_change"], bool):
        raise ValueError("invalid_review_scope")
    components = value["changed_components"]
    if not isinstance(components, list) or not components:
        raise ValueError("invalid_changed_components")
    component_ids = []
    for component in components:
        if not isinstance(component, dict) or set(component) != COMPONENT:
            raise ValueError("invalid_changed_component")
        component_ids.append(_identifier(component["component_id"], "component_id"))
        if component["kind"] not in COMPONENT_KINDS:
            raise ValueError("invalid_changed_component")
    if len(component_ids) != len(set(component_ids)):
        raise ValueError("duplicate_component_id")
    boundaries = value["declared_boundaries"]
    if not isinstance(boundaries, list):
        raise ValueError("invalid_declared_boundaries")
    checked_boundaries = [_safe_text(item, "declared_boundary", limit=160) for item in boundaries]
    if len(checked_boundaries) != len(set(checked_boundaries)):
        raise ValueError("duplicate_declared_boundary")
    return value


def _validate_git_facts(value: Any, component_ids: set[str], *, allow_canonical_run_ids: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != GIT_FACTS:
        raise ValueError("invalid_review_git_facts")
    if value["source_tool"] != "git_facts_collector" or not isinstance(value["working_tree_clean"], bool):
        raise ValueError("invalid_review_git_facts")
    _source_run_id(value["source_run_id"], "git_source_run_id", allow_canonical=allow_canonical_run_ids)
    changed = _identifiers(value["changed_component_ids"], "changed_component_id")
    if not set(changed).issubset(component_ids):
        raise ValueError("git_component_outside_scope")
    return value


def _validate_evidence(value: Any, *, allow_canonical_run_ids: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != EVIDENCE:
        raise ValueError("invalid_review_evidence")
    if value["source_tool"] != "evidence_package_builder" or not isinstance(value["lineage_complete"], bool):
        raise ValueError("invalid_review_evidence")
    _source_run_id(value["source_run_id"], "evidence_source_run_id", allow_canonical=allow_canonical_run_ids)
    _hash(value["content_hash"], "evidence_content_hash")
    for field in ("observed_evidence_refs", "candidate_evidence_refs", "missing_evidence_ids", "unknown_ids"):
        _identifiers(value[field], field[:-1])
    if set(value["observed_evidence_refs"]) & set(value["candidate_evidence_refs"]):
        raise ValueError("evidence_reference_state_conflict")
    return value


def _validate_checks(value: Any, observed_refs: set[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("invalid_required_checks")
    seen: set[str] = set()
    for check in value:
        if not isinstance(check, dict) or set(check) != CHECK:
            raise ValueError("invalid_required_check")
        check_id = _identifier(check["check_id"], "check_id")
        if check_id in seen:
            raise ValueError("duplicate_check_id")
        seen.add(check_id)
        if check["check_type"] not in CHECK_TYPES or check["status"] not in CHECK_STATUSES or check["source_tool"] not in CHECK_SOURCES:
            raise ValueError("invalid_required_check")
        refs = _identifiers(check["evidence_refs"], "check_evidence_ref")
        if check["status"] in {"passed", "failed"}:
            if not refs or not set(refs).issubset(observed_refs):
                raise ValueError("observed_check_requires_observed_evidence")
            if check["check_type"] == "test" and check["source_tool"] != "test_result_parser":
                raise ValueError("test_check_requires_test_parser")
            if check["check_type"] == "git" and check["source_tool"] != "git_facts_collector":
                raise ValueError("git_check_requires_git_facts")
            if check["check_type"] in {"schema", "manual"} and check["source_tool"] == "none":
                raise ValueError("observed_check_requires_source_tool")
        elif check["source_tool"] != "none" or refs:
            raise ValueError("unobserved_check_must_not_claim_evidence")
    return value


def _profile(scope: dict[str, Any], evidence: dict[str, Any], checks: list[dict[str, Any]]) -> tuple[str, list[str]]:
    evidence_risk = (
        not evidence["lineage_complete"]
        or bool(evidence["missing_evidence_ids"])
        or bool(evidence["unknown_ids"])
        or any(check["status"] in {"not_run", "unknown"} for check in checks)
    )
    if evidence_risk:
        return "evidence_risk", ["incomplete_or_unknown_evidence"]
    if scope["change_size"] == "cross_boundary" or len(scope["declared_boundaries"]) > 1:
        return "cross_boundary", ["declared_cross_boundary_scope"]
    if scope["contract_change"] or any(component["kind"] == "contract" for component in scope["changed_components"]):
        return "contract_change", ["declared_contract_change"]
    return "local", ["bounded_local_scope"]


def _profile_details(profile: str) -> tuple[list[str], list[str]]:
    if profile == "evidence_risk":
        return ["evidence_lineage_visible", "unknowns_preserved", "not_run_not_promoted"], ["summary", "evidence_ledger", "unknowns"]
    if profile == "cross_boundary":
        return ["boundary_ownership_visible", "required_checks_visible", "unknowns_preserved"], ["summary", "boundary_map", "ownership_map", "evidence_ledger"]
    if profile == "contract_change":
        return ["contract_change_visible", "negative_evidence_visible", "unknowns_preserved"], ["summary", "semantic_contract_diff", "negative_evidence", "evidence_ledger"]
    return ["scope_is_bounded", "required_checks_visible", "unknowns_preserved"], ["summary", "scoped_evidence", "required_checks"]


def _validate_contract_comparison(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"availability", "unavailable_reason_id", "baseline", "candidate", "added_field_ids", "removed_field_ids", "changed_field_ids"}:
        raise ValueError("invalid_contract_comparison")
    availability = value["availability"]
    if availability == "unavailable":
        if not isinstance(value["unavailable_reason_id"], str):
            raise ValueError("invalid_contract_comparison")
        _identifier(value["unavailable_reason_id"], "comparison_unavailable_reason")
        if any(value[field] is not None for field in ("baseline", "candidate", "added_field_ids", "removed_field_ids", "changed_field_ids")):
            raise ValueError("unavailable_comparison_must_not_claim_delta")
        return value
    if availability != "available" or value["unavailable_reason_id"] is not None:
        raise ValueError("invalid_contract_comparison")
    for endpoint in ("baseline", "candidate"):
        manifest = value[endpoint]
        if not isinstance(manifest, dict) or set(manifest) != {"contract_id", "version_label", "content_hash"}:
            raise ValueError("invalid_contract_manifest")
        _identifier(manifest["contract_id"], f"{endpoint}_contract_id")
        _version_label(manifest["version_label"], f"{endpoint}_version_label")
        _hash(manifest["content_hash"], f"{endpoint}_content_hash")
    if value["baseline"]["content_hash"] == value["candidate"]["content_hash"]:
        raise ValueError("contract_comparison_requires_distinct_hashes")
    field_sets = {}
    for field in ("added_field_ids", "removed_field_ids", "changed_field_ids"):
        field_sets[field] = set(_identifiers(value[field], field[:-1]))
    if not any(field_sets.values()):
        raise ValueError("contract_comparison_requires_declared_delta")
    if any(field_sets[left] & field_sets[right] for left, right in (("added_field_ids", "removed_field_ids"), ("added_field_ids", "changed_field_ids"), ("removed_field_ids", "changed_field_ids"))):
        raise ValueError("contract_delta_field_state_conflict")
    return value


def _evidence_ledger(evidence: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for state, field in (("observed", "observed_evidence_refs"), ("candidate", "candidate_evidence_refs"), ("missing", "missing_evidence_ids"), ("unknown", "unknown_ids")):
        rows.extend({"row_id": f"LEDGER_{state.upper()}_{reference}", "kind": "evidence_reference", "state": state, "evidence_refs": [reference]} for reference in evidence[field])
    for check in sorted(checks, key=lambda item: item["check_id"]):
        state = "observed" if check["status"] in {"passed", "failed"} else check["status"]
        rows.append({"row_id": f"LEDGER_CHECK_{check['check_id']}", "kind": "required_check", "state": state, "check_id": check["check_id"], "status": check["status"], "evidence_refs": check["evidence_refs"]})
    return {
        "contract_version": "1.0.0",
        "derived": True,
        "authoritative_input": "caller_retained_evidence",
        "rows": sorted(rows, key=lambda item: item["row_id"]),
    }


def _contract_delta(value: dict[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {"status": "not_applicable", "reason": "no_contract_comparison_declared"}
    if value["availability"] == "unavailable":
        return {"status": "unavailable", "unavailable_reason_id": value["unavailable_reason_id"]}
    return {
        "status": "structural_delta",
        "baseline": value["baseline"],
        "candidate": value["candidate"],
        "added_field_ids": sorted(value["added_field_ids"]),
        "removed_field_ids": sorted(value["removed_field_ids"]),
        "changed_field_ids": sorted(value["changed_field_ids"]),
        "compatibility_assessment": "not_in_p1",
    }


def build_review_package(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate compact provenance and derive a non-authoritative ReviewPackage."""
    if not isinstance(payload, dict) or set(payload) != ROOT or payload.get("contract_version") != "1.0.0":
        raise ValueError("invalid_review_build_input")
    objective = _safe_text(payload["objective"], "objective", limit=1000)
    scope = _validate_scope(payload["scope"])
    component_ids = {component["component_id"] for component in scope["changed_components"]}
    git_facts = _validate_git_facts(payload["git_facts"], component_ids)
    evidence = _validate_evidence(payload["evidence"])
    checks = _validate_checks(payload["required_checks"], set(evidence["observed_evidence_refs"]))
    profile, activation_reasons = _profile(scope, evidence, checks)
    invariants, derived_views = _profile_details(profile)
    package_hash = stable_hash(payload)
    findings = []
    for check in sorted(checks, key=lambda item: item["check_id"]):
        evidence_state = "observed" if check["status"] in {"passed", "failed"} else check["status"]
        findings.append({
            "finding_id": f"FINDING_{check['check_id']}",
            "kind": "required_check_status",
            "status": check["status"],
            "evidence_state": evidence_state,
            "evidence_refs": check["evidence_refs"],
        })
    unknowns = sorted(set(evidence["missing_evidence_ids"] + evidence["unknown_ids"] + [
        check["check_id"] for check in checks if check["status"] in {"not_run", "unknown"}
    ]))
    evidence_refs = sorted(set(evidence["observed_evidence_refs"] + evidence["candidate_evidence_refs"] + [
        reference for check in checks for reference in check["evidence_refs"]
    ]))
    return {
        "contract_version": "1.0.0",
        "review_package_id": f"REVIEW_{package_hash[:12].upper()}",
        "objective": objective,
        "diagnosis": {"review_profile": profile, "activation_reasons": activation_reasons, "deterministic": True},
        "review_profile": profile,
        "affected_invariants": invariants,
        "affected_boundaries": sorted(scope["declared_boundaries"]),
        "required_checks": sorted(checks, key=lambda item: item["check_id"]),
        "findings": findings,
        "unknowns": unknowns,
        "evidence_refs": evidence_refs,
        "derived_view_plan": {"views": derived_views, "rendering": "not_in_p0", "authoritative_input": "caller_retained_evidence"},
        "authority": {
            "evidence_manifest_authoritative": True,
            "review_package_status": "derived",
            "promotion_authority": "human_or_ai_os_only",
            "model_invoked": False,
            "source_mutation": False,
            "root_cause_inferred": False,
        },
        "evidence_export": {"format": "review_package_v1", "input_sha256": package_hash, "git_source_run_id": git_facts["source_run_id"], "evidence_source_run_id": evidence["source_run_id"]},
    }


def build_review_package_v1_1(payload: dict[str, Any]) -> dict[str, Any]:
    """Add a derived ledger and structural-only contract delta without changing P0."""
    if not isinstance(payload, dict) or set(payload) != P1_ROOT or payload.get("contract_version") != "1.1.0":
        raise ValueError("invalid_review_build_input")
    comparison = payload["contract_comparison"]
    if comparison is not None:
        comparison = _validate_contract_comparison(comparison)
    base_payload = {key: payload[key] for key in ROOT}
    base_payload["contract_version"] = "1.0.0"
    base = build_review_package(base_payload)
    package_hash = stable_hash(payload)
    base.update({
        "contract_version": "1.1.0",
        "review_package_id": f"REVIEW_{package_hash[:12].upper()}",
        "derived_view_plan": {**base["derived_view_plan"], "rendering": "not_in_p1"},
        "evidence_ledger": _evidence_ledger(payload["evidence"], payload["required_checks"]),
        "contract_delta": _contract_delta(comparison),
        "evidence_export": {
            "format": "review_package_v1_1",
            "input_sha256": package_hash,
            "git_source_run_id": payload["git_facts"]["source_run_id"],
            "evidence_source_run_id": payload["evidence"]["source_run_id"],
        },
    })
    return base


def build_review_package_v1_2(payload: dict[str, Any]) -> dict[str, Any]:
    """Versioned lineage repair for canonical LDW ToolResult run IDs only."""
    if not isinstance(payload, dict) or set(payload) != P1_ROOT or payload.get("contract_version") != "1.2.0":
        raise ValueError("invalid_review_build_input")
    comparison = payload["contract_comparison"]
    if comparison is not None:
        comparison = _validate_contract_comparison(comparison)
    objective = _safe_text(payload["objective"], "objective", limit=1000)
    scope = _validate_scope(payload["scope"])
    component_ids = {component["component_id"] for component in scope["changed_components"]}
    git_facts = _validate_git_facts(payload["git_facts"], component_ids, allow_canonical_run_ids=True)
    evidence = _validate_evidence(payload["evidence"], allow_canonical_run_ids=True)
    checks = _validate_checks(payload["required_checks"], set(evidence["observed_evidence_refs"]))
    profile, activation_reasons = _profile(scope, evidence, checks)
    invariants, derived_views = _profile_details(profile)
    package_hash = stable_hash(payload)
    findings = []
    for check in sorted(checks, key=lambda item: item["check_id"]):
        findings.append({"finding_id": f"FINDING_{check['check_id']}", "kind": "required_check_status", "status": check["status"], "evidence_state": "observed" if check["status"] in {"passed", "failed"} else check["status"], "evidence_refs": check["evidence_refs"]})
    unknowns = sorted(set(evidence["missing_evidence_ids"] + evidence["unknown_ids"] + [check["check_id"] for check in checks if check["status"] in {"not_run", "unknown"}]))
    evidence_refs = sorted(set(evidence["observed_evidence_refs"] + evidence["candidate_evidence_refs"] + [reference for check in checks for reference in check["evidence_refs"]]))
    return {
        "contract_version": "1.2.0", "review_package_id": f"REVIEW_{package_hash[:12].upper()}", "objective": objective,
        "diagnosis": {"review_profile": profile, "activation_reasons": activation_reasons, "deterministic": True}, "review_profile": profile,
        "affected_invariants": invariants, "affected_boundaries": sorted(scope["declared_boundaries"]), "required_checks": sorted(checks, key=lambda item: item["check_id"]), "findings": findings,
        "unknowns": unknowns, "evidence_refs": evidence_refs,
        "derived_view_plan": {"views": derived_views, "rendering": "not_in_p1", "authoritative_input": "caller_retained_evidence"},
        "authority": {"evidence_manifest_authoritative": True, "review_package_status": "derived", "promotion_authority": "human_or_ai_os_only", "model_invoked": False, "source_mutation": False, "root_cause_inferred": False},
        "evidence_ledger": _evidence_ledger(evidence, checks), "contract_delta": _contract_delta(comparison),
        "evidence_export": {"format": "review_package_v1_2", "input_sha256": package_hash, "git_source_run_id": git_facts["source_run_id"], "evidence_source_run_id": evidence["source_run_id"]},
    }


def review_build(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    try:
        data = build_review_package(payload) if payload.get("contract_version") == "1.0.0" else build_review_package_v1_1(payload) if payload.get("contract_version") == "1.1.0" else build_review_package_v1_2(payload)
    except ValueError as exc:
        return result("review_package_builder", "stdin", raw, {}, status="invalid_input", errors=[{"code": str(exc)}])
    return result("review_package_builder", "stdin", raw, data)


def _markdown_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def _validate_authority(value: Any) -> None:
    expected = {
        "evidence_manifest_authoritative": True,
        "review_package_status": "derived",
        "promotion_authority": "human_or_ai_os_only",
        "model_invoked": False,
        "source_mutation": False,
        "root_cause_inferred": False,
    }
    if value != expected:
        raise ValueError("invalid_review_package_authority")


def _validate_render_package(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("contract_version") not in {"1.0.0", "1.1.0", "1.2.0"}:
        raise ValueError("unsupported_review_package_version")
    version = value["contract_version"]
    if set(value) != (P0_PACKAGE_FIELDS if version == "1.0.0" else P1_PACKAGE_FIELDS):
        raise ValueError("invalid_review_package")
    _identifier(value["review_package_id"], "review_package_id")
    if not value["review_package_id"].startswith("REVIEW_"):
        raise ValueError("invalid_review_package")
    _safe_text(value["objective"], "review_package_objective", limit=1000)
    if value["review_profile"] not in PROFILES or not isinstance(value["diagnosis"], dict) or value["diagnosis"].get("review_profile") != value["review_profile"] or value["diagnosis"].get("deterministic") is not True:
        raise ValueError("invalid_review_package")
    if not all(isinstance(item, str) for item in value["affected_invariants"] + value["affected_boundaries"] + value["unknowns"] + value["evidence_refs"]):
        raise ValueError("invalid_review_package")
    _validate_checks(value["required_checks"], set(value["evidence_refs"]))
    if not isinstance(value["derived_view_plan"], dict) or value["derived_view_plan"].get("authoritative_input") != "caller_retained_evidence":
        raise ValueError("invalid_review_package")
    _validate_authority(value["authority"])
    export = value["evidence_export"]
    expected_export_format = {
        "1.0.0": "review_package_v1",
        "1.1.0": "review_package_v1_1",
        "1.2.0": "review_package_v1_2",
    }[version]
    if (
        not isinstance(export, dict)
        or set(export) != {"format", "input_sha256", "git_source_run_id", "evidence_source_run_id"}
        or export["format"] != expected_export_format
    ):
        raise ValueError("invalid_review_package")
    _hash(export["input_sha256"], "review_package_input_hash")
    _source_run_id(
        export["git_source_run_id"],
        "git_source_run_id",
        allow_canonical=version == "1.2.0",
    )
    _source_run_id(
        export["evidence_source_run_id"],
        "evidence_source_run_id",
        allow_canonical=version == "1.2.0",
    )
    if version in {"1.1.0", "1.2.0"}:
        ledger = value["evidence_ledger"]
        if not isinstance(ledger, dict) or ledger.get("derived") is not True or ledger.get("authoritative_input") != "caller_retained_evidence" or not isinstance(ledger.get("rows"), list):
            raise ValueError("invalid_review_ledger")
        if not isinstance(value["contract_delta"], dict) or value["contract_delta"].get("status") not in {"not_applicable", "unavailable", "structural_delta"}:
            raise ValueError("invalid_contract_delta")
    return value


def _markdown_checks(checks: list[dict[str, Any]]) -> list[str]:
    rows = ["| Check | Type | Status | Evidence |", "| --- | --- | --- | --- |"]
    for check in checks:
        state = "OBSERVED" if check["status"] in {"passed", "failed"} else check["status"].upper()
        refs = ", ".join(check["evidence_refs"]) or "—"
        rows.append(f"| {check['check_id']} | {check['check_type']} | {check['status'].upper()} | {state}: {refs} |")
    return rows


def _markdown_delta(delta: dict[str, Any]) -> list[str]:
    status = delta["status"]
    if status == "not_applicable":
        return ["- Status: NOT_APPLICABLE", "- Reason: no contract comparison was declared."]
    if status == "unavailable":
        return ["- Status: UNAVAILABLE", f"- Reason ID: {delta['unavailable_reason_id']}"]
    return [
        "- Status: STRUCTURAL_DELTA (caller-declared; compatibility is not assessed).",
        f"- Baseline: {delta['baseline']['contract_id']} @ {delta['baseline']['version_label']}",
        f"- Candidate: {delta['candidate']['contract_id']} @ {delta['candidate']['version_label']}",
        f"- Added fields: {', '.join(delta['added_field_ids']) or '—'}",
        f"- Removed fields: {', '.join(delta['removed_field_ids']) or '—'}",
        f"- Changed fields: {', '.join(delta['changed_field_ids']) or '—'}",
    ]


def render_markdown(review_package: dict[str, Any]) -> str:
    """Render a verified ReviewPackage as deterministic, non-authoritative Markdown."""
    package = _validate_render_package(review_package)
    lines = [
        f"# LDW Review Package {package['review_package_id']}",
        "",
        "## Scope",
        f"- Objective: {_markdown_text(package['objective'])}",
        f"- Profile: {package['review_profile']}",
        f"- Boundaries: {', '.join(package['affected_boundaries']) or '—'}",
        f"- Invariants: {', '.join(package['affected_invariants']) or '—'}",
        "",
        "## Required checks",
        *_markdown_checks(package["required_checks"]),
        "",
        "## Evidence states",
        f"- Observed/candidate references: {', '.join(package['evidence_refs']) or '—'}",
        f"- Missing or unknown IDs: {', '.join(package['unknowns']) or '—'}",
    ]
    if package["contract_version"] in {"1.1.0", "1.2.0"}:
        lines.extend(["", "## Contract delta", *_markdown_delta(package["contract_delta"])])
        ledger_rows = package["evidence_ledger"]["rows"]
        lines.extend(["", "## Evidence ledger", f"- Derived rows: {len(ledger_rows)}; caller-retained evidence remains authoritative."])
    lines.extend([
        "",
        "## Authority limits",
        "- This Markdown is derived from the supplied ReviewPackage; it is not evidence authority.",
        "- No model was invoked; this renderer cannot mutate source, infer root cause, promote, merge, or decide review outcome.",
        "",
    ])
    return "\n".join(lines)


def _html_list(items: list[str]) -> str:
    if not items:
        return "<p>—</p>"
    return "<ul>" + "".join(f"<li>{html_escape(item)}</li>" for item in items) + "</ul>"


def _html_checks(checks: list[dict[str, Any]]) -> str:
    rows = []
    for check in checks:
        state = "OBSERVED" if check["status"] in {"passed", "failed"} else check["status"].upper()
        refs = ", ".join(check["evidence_refs"]) or "—"
        rows.append(
            "<tr>"
            f"<td>{html_escape(check['check_id'])}</td>"
            f"<td>{html_escape(check['check_type'])}</td>"
            f"<td>{html_escape(check['status'].upper())}</td>"
            f"<td>{html_escape(state)}</td>"
            f"<td>{html_escape(refs)}</td>"
            "</tr>"
        )
    return "<table><thead><tr><th>Check</th><th>Type</th><th>Status</th><th>Evidence state</th><th>References</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _html_delta(delta: dict[str, Any]) -> str:
    status = delta["status"]
    if status == "not_applicable":
        return "<p><strong>NOT_APPLICABLE</strong>: no contract comparison was declared.</p>"
    if status == "unavailable":
        return f"<p><strong>UNAVAILABLE</strong>: {html_escape(delta['unavailable_reason_id'])}</p>"
    rows = [
        ("Baseline", f"{delta['baseline']['contract_id']} @ {delta['baseline']['version_label']}"),
        ("Candidate", f"{delta['candidate']['contract_id']} @ {delta['candidate']['version_label']}"),
        ("Added fields", ", ".join(delta["added_field_ids"]) or "—"),
        ("Removed fields", ", ".join(delta["removed_field_ids"]) or "—"),
        ("Changed fields", ", ".join(delta["changed_field_ids"]) or "—"),
    ]
    detail = "".join(f"<dt>{html_escape(label)}</dt><dd>{html_escape(value)}</dd>" for label, value in rows)
    return "<p><strong>STRUCTURAL_DELTA</strong>: caller-declared; compatibility is not assessed.</p><dl>" + detail + "</dl>"


def render_html(review_package: dict[str, Any]) -> str:
    """Render a validated ReviewPackage as self-contained, non-interactive HTML."""
    package = _validate_render_package(review_package)
    boundaries = ", ".join(package["affected_boundaries"]) or "—"
    evidence_refs = ", ".join(package["evidence_refs"]) or "—"
    unknowns = ", ".join(package["unknowns"]) or "—"
    sections = [
        "<!doctype html>",
        '<html lang="en">',
        "<head><meta charset=\"utf-8\"><title>LDW Review Package</title></head>",
        "<body><main>",
        f"<h1>LDW Review Package {html_escape(package['review_package_id'])}</h1>",
        "<section><h2>Scope</h2>",
        f"<p><strong>Objective:</strong> {html_escape(package['objective'])}</p>",
        f"<p><strong>Profile:</strong> {html_escape(package['review_profile'])}</p>",
        f"<p><strong>Boundaries:</strong> {html_escape(boundaries)}</p>",
        "<h3>Invariants</h3>",
        _html_list(package["affected_invariants"]),
        "</section>",
        "<section><h2>Required checks</h2>",
        _html_checks(package["required_checks"]),
        "</section>",
        "<section><h2>Evidence states</h2>",
        f"<p><strong>Observed/candidate references:</strong> {html_escape(evidence_refs)}</p>",
        f"<p><strong>Missing or unknown IDs:</strong> {html_escape(unknowns)}</p>",
        "</section>",
    ]
    if package["contract_version"] in {"1.1.0", "1.2.0"}:
        sections.extend([
            "<section><h2>Contract delta</h2>", _html_delta(package["contract_delta"]), "</section>",
            "<section><h2>Evidence ledger</h2>",
            f"<p>Derived rows: {len(package['evidence_ledger']['rows'])}; caller-retained evidence remains authoritative.</p>",
            "</section>",
        ])
    sections.extend([
        "<section><h2>Authority limits</h2>",
        "<p>This HTML is derived from the supplied ReviewPackage; it is not evidence authority.</p>",
        "<p>No model was invoked; this renderer cannot mutate source, infer root cause, promote, merge, or decide review outcome.</p>",
        "</section>",
        "</main></body></html>",
    ])
    return "\n".join(sections)


def review_render(payload: dict[str, Any]) -> dict[str, Any]:
    raw = canonical_json(payload)
    try:
        if not isinstance(payload, dict) or set(payload) != RENDER_ROOT or payload.get("contract_version") != "1.0.0" or payload.get("format") not in {"markdown", "html"}:
            raise ValueError("invalid_review_render_input")
        artifact = render_markdown(payload["review_package"]) if payload["format"] == "markdown" else render_html(payload["review_package"])
        data = {
            "contract_version": "1.0.0",
            "format": payload["format"],
            "artifact": artifact,
            "artifact_sha256": sha256(artifact),
            "authority": {"source_package_authoritative": False, "rendered_artifact_status": "derived", "model_invoked": False, "source_mutation": False, "review_outcome_decided": False},
        }
    except ValueError as exc:
        return result("review_package_renderer", "stdin", raw, {}, status="invalid_input", errors=[{"code": str(exc)}])
    return result("review_package_renderer", "stdin", raw, data)
