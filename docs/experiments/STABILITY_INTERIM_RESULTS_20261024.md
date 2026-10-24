# Stability investigation: preserved failures before v3 confirmation

**Stable self-evolution has not been established.** The completed investigations
below are negative or diagnostic evidence. The separately preregistered
[v3 official-task confirmation](STABILITY_PROTOCOL_V3_20261024.md) must report its
own final outcome; this document does not count future planned work as completed.

| Completed investigation | Actual physical cost | Outcome |
| --- | --- | --- |
| v1 integration 001 | 2 diagnostic episodes | Scalar audit used wxyz instead of pinned runtime xyzw; stopped before training |
| v1 multiseed attempt 002 | 6 first-round jobs, 3,686,400 transitions, 14,892 completed training episodes; 2 diagnostic episodes | 5 finite-loss audits passed; third continual seed failed at updates 112/113; zero validation/test |
| v2 nominal full-horizon measurement calibration | 24 diagnostic episodes, zero updates | Original instantaneous reach 12/12, low-speed 0.30 s hold 0/12; open gripper 0/12 both; calibration FAILED; v2 confirmation NOT_RUN |
| Official-task metric calibration | 24 fresh diagnostic episodes, zero updates | Original official success 12/12, open gripper 0/12; crossed GPU allocation and independent audit PASS; holding NOT_MEASURED after success termination |

## What failed numerically

All six v1 candidates actually changed weights, and all final actor/critic tensors
were finite. Nevertheless, one learning trajectory proposed actions reaching
**148,719,869,624,320 raw units**, with a dense reward minimum of
**-9.205734111126644e20**, followed by infinite value losses at optimizer
updates **112/113**. The collector accepted finite actions because upstream action
bounds are infinite; checking only NaN/Inf did not contain large finite feedback.
The value-loss audit rejected this trajectory and the registered driver stopped
before reading any private validation or heldout result. No failed seed is omitted.

New code applies the same componentwise +/-1000 numerical envelope to every
training/evaluation arm, archives both proposed and applied actions, independently
reconstructs clipping, and stops the learner immediately on nonfinite loss.
These measures do not guarantee stable learning or mechanical safety. Their
effectiveness and any performance gain require the fresh registered experiment.

## What the measurement calibration means

The published pretrained lift policy can reach the goal on the nominal task but
does not meet the stronger low-speed holding criterion in this calibration. Its
full-horizon traces show continued motion after goal reach. Treating that checkpoint
as an already validated holding oracle was unjustified. The v2 calibration remains
failed; its holding threshold is not relaxed and its confirmation is not launched.

The task specification asks for improvement on the official lift task. The v3
registration therefore explicitly makes repeated official-task gain the primary
question before new training, with all earlier failures disclosed. It preserves
the original upstream success predicate/termination and openly versions the shared
numerical action envelope. A v3 positive result would support bounded repeatable
task adaptation, not low-speed holding, general recursive self-improvement or
autonomous invention of a learning algorithm.

## Inspectable evidence and verification

- [Integration 001 archive manifest](../evidence/stability-preflight-20261024/manifest.json).
- [All six v1 training jobs, including the failed trajectory](../evidence/stability-v1-numerical-failure-20261024/manifest.json): 1,352 raw files, source archive, 1,200 lossless transition chunks, process logs, checkpoint metadata and numerical diagnosis. Model tensors stay outside Git under their separate NVIDIA terms.
- [Both measurement calibrations](../evidence/stability-calibration-20261024/manifest.json): all 48 raw physical episodes and both frozen source snapshots.

Archive verification checks SHA256, separately unpacks the raw data, rechecks the
registered source bytes and recomputes physical episode outcomes and safety.
Supplying a NumPy interpreter additionally recomputes transition values, continuity,
physical mass range, reservations, completed/unfinished training cost, public rewards
and train-only scheduler decisions without requiring licensed model tensors:

```bash
uv run python scripts/verify_stability_delivery.py \
  --evidence docs/evidence/stability-v1-numerical-failure-20261024 \
  --output /tmp/peb-failure-recheck \
  --numpy-python /absolute/path/to/python-with-numpy
```

The public numeric audit deliberately reports `finite_optimizer_losses: false`
and `nonfinite_loss_updates: [112, 113]` for the failed seed. `RAW_DATA_VERIFIED`
means that the failure is reproducible from archived values, not that the learner
was stable. The private tensor audit additionally requires separately downloaded
original/derived checkpoint files; no weights are redistributed.
