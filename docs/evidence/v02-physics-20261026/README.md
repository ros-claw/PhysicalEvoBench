# v0.2 physics diagnosis evidence — 2026-10-26

**Engineering/public audit PASS; W3 reference calibration FAILED. No stable self-evolution claim.**

153 actual diagnostic episodes, 35,333 control steps, 141,332 exposed post-physics samples, 73 sequential native processes on shared GPU0. No new training transitions or Agent learning comparison. A separate36-episode reservation was cancelled before any native launch (zero actual episodes); it is retained, not added to actual cost.

| Run suffix | Actual episodes | Role |
|---|---:|---|
| smoke-001 / smoke-002 | 2 / 2 | Instrument integration;002 adds actual float32 target readback |
| representatives-001 | 16 | Eight selected historical cases ×two new execution layers |
| repeatability-001 | 96 | 16 conditions ×three repeats ×two startup modes |
| reachability-001 | 0 | Cancelled before launch; metadata/inference-config extension |
| reachability-002 | 36 | Original / GeometryExpert / OpenGripper ×12 new conditions |
| minimal-repro-001 | 1 | Same source/model/condition, severe event recurred; not bitwise replay |

In selected representative cases, NumericalOnly had3/8 severe events and2/8 instant arrivals; TargetBounded had0/8 severe events and0/8 arrivals, with two remaining >1mm state violations. W2 had no successful episodes and has a floor effect. W3 had0/12 effective holds in every controller arm; no usable positive reference. These development scores do not change historical results or enter a new efficacy study.

Two lossless data archives (each below48MiB), source archives, manifest and SHA256SUMS preserve2,408 raw/derived files. Licensed model weights and HDF5 recordings are excluded. Inference YAML is hash-bound in reachability-002; earlier registrations predate that additional binding. Smoke-001 records theoretical target-envelope results rather than post-write float32 readback, and is disclosed as the earlier instrumentation version.

Frozen source commits and the minimal-reproduction launcher are included. Observations, contacts, processed/applied targets, live limits, USD metadata, pre-reset terminals, reservations, launch commands, process return codes and shared GPU workload observations remain inspectable. Implicit-actuator computed/applied torque is not a measured solver joint effort. Contact sensors do not establish complete collision safety or unique causal attribution.

[Independent extraction audit receipt](public_delivery_audit.json): PASS,2,408 file hashes,426 registered source-file checks,153 completed physical episodes plus the zero-episode cancellation. The audit recomputes action mapping, position/rate targets, mass, substep coverage, pre-reset terminal equality, upstream completion, repeatability summaries, W3 gate and CSV. No licensed weights or simulation startup required:

```bash
uv run python scripts/verify_stability_delivery.py \
  --evidence docs/evidence/v02-physics-20261026 \
  --output /tmp/peb-v02-independent-NEW
```

Use a new output directory. The published receipt is a record, not a substitute for rerunning verification.

Full Chinese results: [implementation report](../../implementation/V02_阶段实施报告_20261026.md), [physical diagnosis](../../experiments/V02_PHYSICS_DIAGNOSIS.md), [calibration](../../experiments/V02_CALIBRATION.md). No external issue, email or vendor message has been sent.
