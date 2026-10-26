# State-based reference calibration — 2026-10-26

**New ten-second reference calibration PASS. Original five-second failure and v1 heavy-load failure preserved. No autonomous-Agent or stable self-evolution result.**

The state-based DLS teacher checks pose, bilateral cube-normal contact and object-follow before lifting. V2 adds bounded joint-feedback integration after verified grasp, without changing robot drives, physics limits or the common target envelope. Every native worker ran sequentially on shared GPU 2; unrelated jobs were retained.

| Completed phase | Actual episodes | Effective holds | Role |
|---|---:|---:|---|
| Five-second development | 4 | 0/4 | Verified grasp, insufficient remaining time for this controller |
| Ten-second v1 development | 4 | 4/4 | Frozen before independent confirmation |
| V1 independent reference | 12 | 6/6 light, 2/6 heavy | Reference Gate FAILED |
| V1 open-gripper | 12 | 0/12 | Full negative control retained |
| Ten-second v2 development | 4 | 4/4 heavy | One bounded integral configuration |
| V2 independent reference | 12 | 6/6 light, 5/6 heavy | Reference Gate PASSED |
| V2 open-gripper | 12 | 0/12 | Same source/task/executor |
| Separate parameter activation | 4 | 4/4 | Baseline, identity, clearance and close-wait variants |
| **Total** | **64** | Separate studies, never pooled | No new training |

Light/heavy mean 0.1/0.4 kg. The registered reference criterion requires at least 5/6 effective holds in each mass stratum, no sampled position violation in the twelve reference episodes, and zero effective holds in the twelve negative controls. Position violation means finger depth >0.001 m or arm depth >0.001 rad; severe stop bounds remain 0.01 m/0.1 rad. No such position violations were observed in these runs. Effective hold requires distance <0.05 m and speed ≤0.2 m/s continuously for at least 0.30 s at control samples.

One v2 heavy episode had instant arrival and only 0.16 s qualifying hold, so it failed. All twelve reference terminal states satisfy the instantaneous position/speed predicate, which alone does not imply task completion. One successful reference temporarily left the goal after its first qualifying window and later returned. These facts are preserved in the additive terminal followup; there is no whole-horizon or unlimited safety guarantee.

The four activation episodes share one condition. Clearance changes same-input command and actual applied target at step 0. Close-wait changes the same-input command at step 210 and actual target after that point. Identity has the same program content but numerical target divergence from step 190; first effective hold is 7.12 s baseline versus 8.92 s identity. This is replay variation, not learned improvement. Activation does not establish parameter efficacy or an independent-condition sample size of four.

64 episodes cover 37 distinct conditions, 31,000 control steps, 124,000 exposed physics samples and 11 native processes. Teacher development is capped at 12, independent v1/v2 confirmations cost 48, and activation is a separate preregistered four-episode stage. Native startup-to-exit wall time totals about 48.67 minutes, including loading; simulated control time is 620 s. Earlier 153 diagnostic episodes are separate. No model training or actual model-driven Agent study ran.

Two lossless data archives, immutable source archives, manifest and SHA256SUMS preserve the complete raw/derived run files. Model weights and HDF5 recordings are excluded. Base checkpoint/gain row.skill_sha256 is inherited legacy context; full effective_controller_sha256 includes registered runtime source, controller type, configuration and task/executor. Identity and variants are checked in controller_identity.json. Frozen reference artifacts are reloaded before fresh native processes and bound to their planned configurations.

PhysX contact aliases return normal components on this pinned installation. Net-normal and cube-filtered normal forces are recorded explicitly in newer sources; tangential force and actual solver joint effort are not measured. Do not interpret the data as complete collision or hardware safety certification.

[Independent extraction receipt](public_delivery_audit.json) verifies the archive manifest/source hashes and recomputes all 64 episodes, state guards, contact/aperture observations, bounded integral, both reference gates, terminal followup, full controller identities and parameter activation. No licensed model or SimulationApp is needed:

```bash
uv run python scripts/verify_stability_delivery.py \
  --evidence docs/evidence/state-reference-20261026 \
  --output /tmp/peb-state-reference-independent-NEW
```

Use a new output directory. The published receipt is not a substitute for rerunning verification. [Full Chinese implementation report](../../implementation/STATE_REFERENCE_实施报告_20261026.md), [v2 preregistration](../../experiments/STATE_REFERENCE_V2_PROTOCOL_20261026.md), [separate activation protocol](../../experiments/REFERENCE_W4_ACTIVATION_PROTOCOL_20261026.md).
