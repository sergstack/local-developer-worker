from __future__ import annotations

import tomllib
from pathlib import Path


def load_policy(path: str | None = None) -> dict:
    default = Path(__file__).parents[2] / "policy.toml"
    with (Path(path) if path else default).open("rb") as handle:
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
