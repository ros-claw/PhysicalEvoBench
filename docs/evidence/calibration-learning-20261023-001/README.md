# Calibration and weight learning: complete 422-episode evidence

**Real weight updates ran; stable performance improvement was not confirmed.**
The initial mixed-policy-worker test scored original **4/32**, learned **10/32**.
A prospectively fixed follow-up used 48 fresh paired conditions, separate per-policy
workers and crossed GPU allocation: **12/48 versus 15/48**, +6.25 pp, conditional
95% interval [-12.5, +25] pp, one-sided exact p=0.3318. Both results remain.

The 422 completed evaluation/diagnostic/demo episodes are separate from training:
614,400 real transitions, 2,467 completed training episodes, 128 unfinished
rollouts. All failed startups, negative geometry controls, source snapshots,
200 training-transition chunks, model metadata and checksums are included.
The original 326-episode phase and the additional 96-episode isolated confirmation
are identified separately; changing evaluation protocols are not pooled into a
single primary significance result.

`summary.json` is the independently recomputed readout. `delivery-verification.json`
records successful fresh extraction and re-audit of all 422 evaluation traces,
all training transitions and official lengths, actual external model tensors,
and 2,001 registered source-file hashes. Its published-file count refers to the
49 archived input files before the readable index files and preserved historical analysis source were added; final
SHA256SUMS covers the complete directory. This is evidence consistency, not a
hostile-process security or universal self-evolution claim.

Full local verification requires the pinned Arena interpreter and the two licensed
external checkpoints at their recorded paths. We do not redistribute weights.

```bash
uv run python scripts/verify_calibration_delivery.py --evidence docs/evidence/calibration-learning-20261023-001 --output .cache/new-delivery-audit
```

Without external weights, add `--skip-private-models`: this rechecks evaluation
traces and training archive hashes while explicitly marking the training tensor/
value re-audit as not performed. It does not reconstruct missing weights.

The actual wrist-camera replay becomes dark during the learned policy; official
upstream outcomes and state traces establish completion. Padded terminal frames
are explicitly labeled and do not represent a physical hold interval. The demo
is post-hoc, two additional episodes, excluded from the 32/48-pair scores.
