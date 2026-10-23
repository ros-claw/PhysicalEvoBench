# Initial calibration and PPO evidence (326 completed evaluation/diagnostic/demo episodes)

Full raw episode traces, all failed attempts, 200 training-transition chunks, source
snapshots, model metadata and checksums. Original and trained weights remain outside
the repository under their inherited licensing terms. Training accounts for 614,400
transitions, 2,467 completed episodes and 128 unfinished rollouts, separately.

The 32-pair mixed-order heldout result is 4/32 original versus 10/32 learned.
The post-hoc order split motivates an additional prospectively registered
96-episode isolated-policy confirmation; that follow-up is not included in this
initial 326-episode archive snapshot. See the protocol and final results document.

The actual wrist-camera replay becomes dark during the learned policy; use official
upstream outcomes and state traces to verify completion. Padded terminal frames are
explicitly labeled and do not represent a physical hold interval.

Full local verification requires the pinned Arena interpreter and the two licensed
external checkpoints at their recorded paths:

```bash
uv run python scripts/verify_calibration_delivery.py --evidence docs/evidence/calibration-learning-20261023-001 --output .cache/new-delivery-audit
```

Without external weights, add `--skip-private-models`: this independently rechecks
all evaluation physics traces and training archive hashes, while explicitly marking
the training tensor/value re-audit as not performed. It does not reconstruct weights.
