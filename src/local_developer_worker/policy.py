from __future__ import annotations

import ipaddress
import os
import socket
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

from .contracts import canonical_json, result


_PROCESS_RUNNER = subprocess.run


def load_policy(path: str | None = None) -> dict:
    default = Path(__file__).parents[2] / "policy.toml"
    configured = path or os.environ.get("LDW_POLICY_PATH")
    global_policy = Path.home() / ".config" / "local-developer-worker" / "policy.toml"
    active = Path(configured) if configured else default
    if not configured and global_policy.is_file():
        try:
            Path.cwd().resolve().relative_to(default.parent.resolve())
        except ValueError:
            active = global_policy
    with active.open("rb") as handle:
        return tomllib.load(handle)


def allowed(policy: dict, capability: str) -> bool:
    return bool(policy.get("automatic", {}).get(capability, False))


def root_allowed(policy: dict, root: str, base: Path | None = None) -> bool:
    roots = policy.get("security", {}).get("allowed_repository_roots", [])
    if not isinstance(roots, list):
        return False
    policy_base = (base or Path.cwd()).resolve()
    candidate = Path(root).resolve()
    try:
        for allowed_root in roots:
            configured = (policy_base / allowed_root).resolve() if not Path(allowed_root).is_absolute() else Path(allowed_root).resolve()
            candidate.relative_to(configured)
            return True
    except (TypeError, ValueError):
        return False
    return False


def _resolved_addresses(
    endpoint: str,
    resolver: Callable[..., list[tuple[Any, ...]]] = socket.getaddrinfo,
) -> tuple[str, tuple[str, ...]]:
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("invalid inference endpoint")
    host = parsed.hostname
    try:
        direct = ipaddress.ip_address(host)
    except ValueError:
        records = resolver(host, parsed.port, type=socket.SOCK_STREAM)
        addresses = {record[4][0] for record in records if len(record) >= 5 and record[4]}
    else:
        addresses = {str(direct)}
    if not addresses:
        raise ValueError("inference endpoint did not resolve")
    normalized = tuple(sorted({str(ipaddress.ip_address(address)) for address in addresses}))
    return host, normalized


def inference_endpoint_policy(
    endpoint: str,
    *,
    resolver: Callable[..., list[tuple[Any, ...]]] = socket.getaddrinfo,
) -> dict[str, Any]:
    raw = canonical_json({"endpoint": endpoint})
    try:
        host, addresses = _resolved_addresses(endpoint, resolver)
        allowed_endpoint = all(ipaddress.ip_address(address).is_loopback for address in addresses)
    except (OSError, TypeError, ValueError):
        host, addresses, allowed_endpoint = None, (), False
    if not allowed_endpoint:
        return result(
            "inference_endpoint_policy",
            "endpoint",
            raw,
            {"endpoint_host": host, "resolved_addresses": list(addresses)},
            status="policy_blocked",
            errors=[{"code": "non_loopback_inference_endpoint"}],
        )
    return result(
        "inference_endpoint_policy",
        "endpoint",
        raw,
        {"endpoint_host": host, "resolved_addresses": list(addresses)},
    )


def local_inference_runtime_policy(
    endpoint: str,
    addresses: tuple[str, ...],
    *,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    runner = runner or _PROCESS_RUNNER
    raw = canonical_json({"endpoint": endpoint, "resolved_addresses": list(addresses)})
    data = {
        "assurance_level": "transport_endpoint_local_verified",
        "transport_endpoint_local_verified": True,
        "local_process_verified": False,
        "local_runtime_verified": False,
        "physical_inference_locality": "not_provable",
    }
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        listener = runner(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            check=False,
        )
        address_tokens = {f"{address}:{port}" for address in addresses} | {
            f"[{address}]:{port}" for address in addresses
        }
        lines = [
            line for line in listener.stdout.splitlines()
            if "LISTEN" in line and any(token in line for token in address_tokens)
        ]
        if listener.returncode or len(lines) != 1:
            raise ValueError("local listener is absent or ambiguous")
        fields = lines[0].split()
        process, pid = fields[0].lower(), fields[1]
        if process != "ollama" or not pid.isdigit():
            raise ValueError("listener is not Ollama")
        process_row = runner(
            ["ps", "-p", pid, "-o", "comm="],
            capture_output=True,
            text=True,
            check=False,
        )
        executable = process_row.stdout.strip()
        if process_row.returncode or Path(executable).name.lower() != "ollama":
            raise ValueError("listener executable is not Ollama")
    except (AttributeError, IndexError, OSError, TypeError, ValueError):
        return result(
            "inference_locality_policy",
            "endpoint",
            raw,
            data,
            status="policy_blocked",
            errors=[{"code": "local_inference_runtime_unverified"}],
        )
    return result(
        "inference_locality_policy",
        "endpoint",
        raw,
        {
            **data,
            "assurance_level": "local_runtime_verified",
            "local_process_verified": True,
            "local_runtime_verified": True,
            "runtime_identity": "ollama",
        },
    )


def _pinned_endpoint(endpoint: str, address: str) -> str:
    parsed = urlsplit(endpoint)
    host = f"[{address}]" if ":" in address else address
    netloc = f"{host}:{parsed.port}" if parsed.port is not None else host
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, ""))


def guarded_inference_call(
    endpoint: str,
    payload: dict[str, Any],
    transport: Callable[[str, dict[str, Any]], Any],
    *,
    resolver: Callable[..., list[tuple[Any, ...]]] = socket.getaddrinfo,
    runtime_verifier: Callable[[str, tuple[str, ...]], dict[str, Any]] | None = local_inference_runtime_policy,
) -> tuple[dict[str, Any], Any | None]:
    endpoint_result = inference_endpoint_policy(endpoint, resolver=resolver)
    if endpoint_result["status"] != "success":
        return endpoint_result, None
    addresses = tuple(endpoint_result["data"]["resolved_addresses"])
    policy_result = endpoint_result
    if runtime_verifier is not None:
        policy_result = runtime_verifier(endpoint, addresses)
        if policy_result["status"] != "success":
            return policy_result, None
    pinned = _pinned_endpoint(endpoint, addresses[0])
    return policy_result, transport(pinned, payload)
