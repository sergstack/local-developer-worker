import socket
import subprocess
import tomllib
import ipaddress
from pathlib import Path

import pytest

from local_developer_worker.policy import guarded_inference_call, inference_endpoint_policy

ROOT = Path(__file__).parents[2]
BASE_COMMIT = "5a3d14654e55c51a60439d1478a227cf1fe5a77b"
POLICY_COMMENT = """# network_access denies outbound network access to external hosts/APIs.
# Loopback-only calls (127.0.0.1, ::1) for local model inference are exempt:
# they never leave the machine, resolve no DNS, and route nowhere external.
# Binding to 0.0.0.0 or any non-loopback address remains prohibited
# regardless of this exemption.
"""


def _resolver(*addresses):
    def resolve(host, port, *, type):
        assert type == socket.SOCK_STREAM
        return [(socket.AF_INET6 if ":" in address else socket.AF_INET, type, 6, "", (address, port or 0)) for address in addresses]

    return resolve


def test_policy_01_policy_file_changes_only_by_approved_comment_and_phase_2_config():
    current = (ROOT / "policy.toml").read_text()
    baseline = subprocess.run(
        ["git", "show", f"{BASE_COMMIT}:policy.toml"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    expected = baseline.replace("network_access = false\n", POLICY_COMMENT + "network_access = false\n")
    expected = expected.replace(
        "change_summarizer_facts_only = true\n",
        "change_summarizer_facts_only = true\nsemantic_log_clustering = false\n",
    )
    expected = expected.replace(
        'code_artifact = "disabled"\n',
        'code_artifact = "disabled"\nmodel = "qwen3:4b"\n'
        'endpoint = "http://127.0.0.1:11435/api/generate"\n',
    )

    assert current == expected
    assert tomllib.loads(current)["semantic"]["enabled"] is False


@pytest.mark.parametrize(
    ("endpoint", "resolver"),
    [
        ("http://127.0.0.1:11434/api/generate", _resolver("203.0.113.1")),
        ("http://[::1]:11434/api/generate", _resolver("203.0.113.1")),
        ("http://localhost:11434/api/generate", _resolver("127.0.0.1", "::1")),
    ],
)
def test_policy_01_accepts_only_loopback_inference_endpoints(endpoint, resolver):
    output = inference_endpoint_policy(endpoint, resolver=resolver)

    assert output["status"] == "success"
    assert output["errors"] == []
    assert output["data"]["resolved_addresses"]


def test_policy_01_actual_localhost_resolves_strictly_to_loopback():
    output = inference_endpoint_policy("http://localhost:11434/api/generate")

    assert output["status"] == "success"
    assert output["data"]["resolved_addresses"]
    assert all(ipaddress.ip_address(address).is_loopback for address in output["data"]["resolved_addresses"])


@pytest.mark.parametrize(
    ("endpoint", "resolver"),
    [
        ("http://0.0.0.0:11434/api/generate", _resolver("127.0.0.1")),
        ("http://203.0.113.20:11434/api/generate", _resolver("127.0.0.1")),
        ("http://model.example:11434/api/generate", _resolver("203.0.113.20")),
        ("http://mixed.example:11434/api/generate", _resolver("127.0.0.1", "203.0.113.20")),
    ],
)
def test_gate_04_rejects_non_loopback_endpoint_before_transport(endpoint, resolver):
    calls = []

    output, response = guarded_inference_call(endpoint, {"events": []}, lambda *args: calls.append(args), resolver=resolver)

    assert output["status"] == "policy_blocked"
    assert output["errors"] == [{"code": "non_loopback_inference_endpoint"}]
    assert response is None
    assert calls == []


def test_gate_04_rejects_resolution_failure_before_transport():
    calls = []

    def failed_resolution(*args, **kwargs):
        raise socket.gaierror("synthetic resolution failure")

    output, response = guarded_inference_call(
        "http://unresolved.example:11434/api/generate",
        {"events": []},
        lambda *args: calls.append(args),
        resolver=failed_resolution,
    )

    assert output["status"] == "policy_blocked"
    assert output["errors"] == [{"code": "non_loopback_inference_endpoint"}]
    assert response is None
    assert calls == []


def test_policy_01_allows_transport_only_after_loopback_guard():
    calls = []

    output, response = guarded_inference_call(
        "http://localhost:11434/api/generate",
        {"events": [{"event_id": "EV-000001"}]},
        lambda endpoint, payload: calls.append((endpoint, payload)) or {"candidate": "observed"},
        resolver=_resolver("127.0.0.1"),
    )

    assert output["status"] == "success"
    assert response == {"candidate": "observed"}
    assert calls == [("http://127.0.0.1:11434/api/generate", {"events": [{"event_id": "EV-000001"}]})]


def test_gate_04_pins_localhost_transport_to_prevalidated_loopback_address():
    calls = []

    output, _ = guarded_inference_call(
        "http://localhost:11434/api/generate",
        {"events": []},
        lambda endpoint, payload: calls.append(endpoint),
        resolver=_resolver("::1"),
    )

    assert output["status"] == "success"
    assert calls == ["http://[::1]:11434/api/generate"]
