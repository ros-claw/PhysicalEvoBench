# PhysicalEvoBench Core — development Alpha contract

**Question.** Within fixed physical and computational budgets, can an Agent turn its own
interaction feedback into persistent executable experience that improves performance on
conditions or tasks excluded from updating, while retaining prior capability?

Scope: `simulated_physics`, `state_observation`, `single_arm`, `fixed_base_model`
(when applicable), `skill_artifact_learning`. PhysX and Franka dependencies remain pinned.
This card defines new experiments; historical five-second failures and ten-second
calibration scores are unchanged. Current calibrated reference: `calibration/state-reference-h10`,
source `c8017dd38996ca5a195ade1d9137c77899be2c56`, normal v2 configuration.

| Contract | Definition |
| --- | --- |
| Statistical units | `episode`: one physical execution; `learning_run`: independent learning from common initial ability and empty memory; `frozen_artifact`: the only cross-instance inheritance |
| P track | Frozen v2 plus clearance 0.08–0.12 m and close wait 0.20–0.70 s; parameter adaptation only |
| S track | Bounded JSON graph of public-state goals, motion/gripper primitives, guards, branches and retries; fixed shared IK, drives and target envelope |
| T0 | Existing `state-reference-h10-v1`, ten seconds, distance <0.05 m, speed ≤0.20 m/s for ≥0.30 s |
| T1 | Separately versioned Pick–Transport–Place; development feasibility precedes independent reference confirmation and transfer claims |
| Participant information | Public poses, velocities, finger aperture and paired **normal** contact; training feedback; never mass truth, seed, heldout labels or evaluator internals |
| Costs | Reserve before execution; failed candidates, validation, resets, model calls/tokens and launch failures remain visible |
| Learning/test boundary | Freeze all snapshots before heldout evaluation; new session and native process; discard transient state after every test condition; no test-informed selection |
| Comparisons | Frozen, score-only search, feedback plus persistent artifact; same initial ability, editable space and physical budget; artifact deletion is paired evaluation, not independent learning |
| Scores | Initial and final numerator/denominator, signed gain, transfer and retention; sparse budget snapshots labeled sparse; risks and costs separately |
| Interpretation | Reactive feedback and reset integral state are not persistent learning. Acceptance does not require positive gains, promotions, or a winning method. |

The initial diagnostic/pilot has at most one learning trajectory per trained method;
condition replays cannot establish cross-learning reliability. Fixed public manifests are
heldout benchmark splits, not a secret evaluation server. Trusted participants only:
API validation and read-only processes are not an adversarial filesystem sandbox.
Measured coordinate-limit events and normal contact are not complete collision or real-robot
safety; tangential forces and actual solver joint effort remain `not_measured`.

Implementation protocol: [Core protocol](docs/core/CORE_PROTOCOL_20261027.md).
Task and interface details: [T0](docs/core/T0_TASK_CARD.md),
[T1](docs/core/T1_TASK_CARD.md), [participant protocol](docs/core/PARTICIPANT_PROTOCOL.md).
No benchmark release or algorithmic efficacy is implied by this development card.
