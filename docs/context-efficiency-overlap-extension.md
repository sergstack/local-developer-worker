# Context-efficiency measurement extension v1.1

This owner-authorized supplemental corpus extends, but does not replace, issue #23's immutable 12-case baseline. `benchmarks/context_overlap_manifest.json` supplies deterministic hash-backed redundancy and negative-control cases for issue #24. Run it with `PYTHONPATH=src python scripts/run_context_overlap_benchmark.py`.

The original runner remains the source for baseline results; it reports zero redundancy reduction when its corpus contains no hashes or duplicate paths. The supplemental runner reports reduction only for its own corpus, verifies critical-file recall, and records the hash of that corpus. No provider calls, production behavior, or public CLI contract is changed.
