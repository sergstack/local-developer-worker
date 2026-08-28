# Testing

The test suite contains unit, contract, golden, integration, security and end-to-end tests. Fixtures must be synthetic or sanitized. Golden tests cover deterministic parsers and invariant tests cover no silent line loss, stable hashes and evidence-linked reporting.

Portfolio contract tests validate all 20 registry entries, exact pytest node IDs, and byte-identical release-gate generation. `python scripts/generate_release_gates.py --check` detects documentation drift. Telemetry tests use isolated journal roots so pytest calls never contaminate the operator's real-session journal.

## Continuous integration

The GitHub Actions workflow runs on pull requests and on `main`. It uses the
locked development environment, then runs the following checks in order:

```bash
uv sync --extra dev --locked
uv run python scripts/validate_schemas.py
uv run python scripts/secret_scan.py
uv build
uv run python -m pytest -rA
```

The build step produces both an sdist and a wheel. Local `dist/` output is
ignored by Git.

## Historical fixture baseline

`scripts/validate_fixtures.py` validates the frozen historical task manifest.
It is intentionally not a blocking CI check: its recorded file-size entries
describe an earlier source revision. Do not rewrite that baseline to match a
later implementation. Any update must be an owner-authorized, versioned
measurement extension with its own migration note and separately reported
results.
