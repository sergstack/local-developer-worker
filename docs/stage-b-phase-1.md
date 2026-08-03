# Stage B Phase 1 regression gate

Phase 1 validates candidate semantic groups; it does not create production groups, enable semantic policy, or route normal CLI traffic to a model. The canonical 10-object registry is `docs/stage_b_gate_registry.json` and contains `POLICY-01`, `REF-01`, `GATE-01` through `GATE-07`, and `NR-01`.

## Run the gated portfolio

```bash
PYTHONPATH=src python scripts/run_stage_b_portfolio.py
```

The runner executes every declared evidence node independently, passes captured runner output through `ldw test parse`, continues after failures, and emits only deterministic evidence metadata. `phase_1_complete` requires all 10 objects plus reconciliation of the registry, reference corpus, semantic policy, schema, and unchanged Stage A safety matrix.

## Loopback enforcement

`POLICY-01` keeps `network_access = false` and `[semantic].enabled = false`. `guarded_inference_call` resolves the endpoint host, rejects empty, wildcard, external, mixed, or failed resolution with `policy_blocked` / `non_loopback_inference_endpoint`, and pins accepted transport calls to the already validated loopback IP to prevent a second DNS resolution.

## Reference corpus and gates

`fixtures/stage_b/reference_events.json` contains sanitized, synthetically noised repository test/CI patterns. `expected_groups.json` accounts for every event through a group or explicit exclusion and declares pairs that must remain separate. Gate code validates externally supplied candidates for source recall, invented references, fallback, payload privacy, origin labels, confidence bounds, and deterministic review; it contains no clustering algorithm.

## Observational model probe

`scripts/run_stage_b_model_probe.py` is separate from gated acceptance. It may be run only against a loopback endpoint after POLICY-01 passes. It sends the sanitized reference payload, stores no raw provider response, and reports only validation status, counts, hashes, and safe error metadata. Its availability or model quality does not rewrite deterministic gate evidence.
