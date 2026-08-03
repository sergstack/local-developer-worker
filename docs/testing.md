# Testing

The test suite contains unit, contract, golden, integration, security and end-to-end tests. Fixtures must be synthetic or sanitized. Golden tests cover deterministic parsers and invariant tests cover no silent line loss, stable hashes and evidence-linked reporting.

Portfolio contract tests validate all 20 registry entries, exact pytest node IDs, and byte-identical release-gate generation. `python scripts/generate_release_gates.py --check` detects documentation drift. Telemetry tests use isolated journal roots so pytest calls never contaminate the operator's real-session journal.
