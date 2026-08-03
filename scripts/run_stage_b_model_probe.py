from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

from local_developer_worker.contracts import canonical_json, stable_hash
from local_developer_worker.policy import guarded_inference_call, load_policy
from local_developer_worker.stage_b_gate import build_inference_payload, validate_candidate_response

ROOT = Path(__file__).parents[1]
RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["groups", "excluded"],
    "properties": {
        "groups": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["group_id", "pattern", "classification", "source_span", "confidence", "origin", "needs_review"],
                "properties": {
                    "group_id": {"type": "string", "pattern": "^SG-[A-Z0-9_-]+$"},
                    "pattern": {"type": "string"},
                    "classification": {"type": "string"},
                    "source_span": {"type": "array", "items": {"type": "string"}, "minItems": 1, "uniqueItems": True},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "origin": {"const": "model-derived"},
                    "needs_review": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        },
        "excluded": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["event_id", "reason"],
                "properties": {"event_id": {"type": "string"}, "reason": {"type": "string"}},
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _transport(endpoint: str, request_payload: dict) -> dict:
    request = urllib.request.Request(
        endpoint,
        data=canonical_json(request_payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=120) as response:
        envelope = json.loads(response.read())
    return json.loads(envelope["response"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an observational qwen3:4b probe separate from the Phase 1 gate")
    parser.add_argument("--policy-path")
    args = parser.parse_args()
    semantic_policy = load_policy(args.policy_path).get("semantic", {})
    endpoint = semantic_policy.get("endpoint")
    model = semantic_policy.get("model")
    if not isinstance(endpoint, str) or not endpoint or not isinstance(model, str) or not model:
        print(canonical_json({"probe_status": "unavailable", "error_type": "invalid_semantic_policy", "raw_response_stored": False}))
        return 2

    fixture_root = ROOT / "fixtures" / "stage_b"
    events = json.loads((fixture_root / "reference_events.json").read_text())["events"]
    truth = json.loads((fixture_root / "expected_groups.json").read_text())
    inference_payload = build_inference_payload(events)
    prompt = (
        "Group repeated failure events by the same concrete failure pattern. "
        "Account for every event exactly once: failure events in groups and non-failure events in excluded. "
        "Never invent event IDs. Keep distinct failure types separate. Return only JSON matching the supplied schema.\n"
        + canonical_json(inference_payload)
    )
    request_payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": RESPONSE_SCHEMA,
        "options": {"temperature": 0},
    }
    try:
        policy_result, candidate = guarded_inference_call(endpoint, request_payload, _transport)
        if policy_result["status"] != "success":
            summary = {"probe_status": "policy_blocked", "policy": policy_result, "model": model}
            print(canonical_json(summary))
            return 2
        validation = validate_candidate_response(events, candidate, ground_truth=truth)
        summary = {
            "probe_status": "accepted" if validation["accepted"] else "rejected",
            "model": model,
            "endpoint_policy": "loopback_only",
            "reference_event_count": len(events),
            "group_count": len(candidate.get("groups", [])),
            "excluded_count": len(candidate.get("excluded", [])),
            "candidate_hash": stable_hash(candidate),
            "validation_errors": validation["errors"],
            "raw_response_stored": False,
        }
        print(canonical_json(summary))
        return 0 if validation["accepted"] else 1
    except urllib.error.HTTPError as exc:
        print(canonical_json({"probe_status": "unavailable", "model": model, "error_type": "HTTPError", "http_status": exc.code, "raw_response_stored": False}))
        return 2
    except (KeyError, TypeError, ValueError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(canonical_json({"probe_status": "unavailable", "model": model, "error_type": type(exc).__name__, "raw_response_stored": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
