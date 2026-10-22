# Temporal skill development evidence

64 real training exploration episodes, 32 independent validation episodes, zero heldout test episodes.
All 128 raw action/state traces, upstream outcomes, parameter snapshots, source hashes and budgets
are in the archives. No model weights are distributed. No actuator strength, mass distribution,
robot model, official success predicate or timeout was changed.

Verify `sha256sum -c SHA256SUMS`, then extract both archives into the same fresh directory:

```bash
mkdir unpacked
tar -xzf exploration.tar.gz -C unpacked
tar -xzf validation.tar.gz -C unpacked
uv run python scripts/audit_temporal_exploration.py --study-dir unpacked/exploration
uv run python scripts/audit_temporal_gate.py --run-dir unpacked/validation --exploration unpacked/exploration
```

Training success gains are not a heldout self-improvement result. The predeclared gate and all
failed candidates are preserved. Original checkpoint and all historical evidence are unchanged.
