# Calibration and weight learning — prospective protocol

This study separates instrument sensitivity, original-task headroom, replay calibration,
and train-only neural adaptation. Historical scores and gates remain unchanged. All
rollouts use the original PhysX Franka joint-position hardware, force limits, 50 Hz,
five-second evaluation timeout and official instantaneous success predicate. Upstream
source pins remain unchanged. These are diagnostic controls, not a reclassification of
previous negative studies.

## Measurement positive control

Twelve fresh paired seeds at 0.1 kg, three randomized arms per seed: original policy
twice and a deliberately degraded policy that keeps its gripper open. Budget 36
completed episodes, with attempts charged before launch. Detectability passes when
original mean success minus degraded success is at least 50 percentage points. This
checks sensitivity to a large known intervention; it does not establish power for a
small effect at 0.8–3.2 kg. Original repeats estimate within-process replay discordance.

## Same-constraint geometry expert

Twelve fresh development conditions, original versus observable-geometry DLS IK FSM,
24 episodes maximum. No mass truth is used by this expert. The original actuator and
joint-position control are retained; the IK computes actions, not a different robot.
At most one correction of an infrastructure/frame bug is permitted, with failed
attempts preserved. Timing/trajectory changes are new development, never heldout.
After development, freeze source and evaluate on 24 new independent conditions
(48 episodes). Report paired outcomes and exact one-sided McNemar probability,
sampled safety and timeouts. Failure of this particular expert is inconclusive about
intrinsic solvability. No controller is called a strong positive control unless it
actually outperforms the original on those new conditions.

## Replay and sampled safety calibration

Twelve fresh conditions with three within-worker original-policy executions each
(36 episodes), then one fresh-process execution for each of the same conditions
(12 episodes). Total 48. Compare full recorded initial observations, positions,
velocities, commands, first actions, and complete action trajectories. The process
comparison tests a reset/order hypothesis, not equivalence or a unique cause.
Run no other tasks on these workers, and leave unrelated GPU jobs alone.

Retain the historical >0.001 coordinate-unit pre-step joint count. Add named-joint
units, maximum depth, integrated depth, exposure duration, per-1000 joint samples
and any-violation episode rate. Report all of them, without selecting a new safety
gate after observing results. Collision and between-sample violations remain
unmeasured. The official success predicate is unchanged; it does not certify a
stable grasp or a post-success hold interval.

## Neural learner

Implement a real PPO weight updater initialized from the pinned model. A trusted
collector sends only public policy/task observations, rewards, dones and timeouts
to a separate learner process; hidden mass, simulator seeds, validation and heldout
results are excluded. The learner has no environment reference. This is payload
isolation, not a hostile-process sandbox. Use official dense training rewards and
training mode (success termination disabled), not evaluation success counts.

Initial bounded training: 128 parallel environments, 200 iterations × 24 steps,
614,400 environment transitions, mass uniformly sampled over 0.8–3.2 kg. Reserve
vector transitions before stepping and count resets/unfinished rollouts separately.
Learning seed 2026102301. Freeze the final checkpoint and parameter-change norm
before validation. A 24-condition validation (48 paired episodes) checks strict
success gain with no increase in historical joint samples. If rejected, retain the
original; still report candidate diagnostic performance transparently. Test retained
policy on 32 fresh paired conditions (64 episodes) after decision freeze. One seed
is an implementation/feasibility study and cannot establish robust multi-seed
self-evolution. Trained weights remain outside the repository under their inherited
licensing terms. No fictitious LLM competitor or zero-token agent is represented
as a learned policy.

Every source revision, runtime failure, process return code, budget reservation,
raw evaluation trace, training transition archive and weight digest must be kept.
Conclusions distinguish changed weights, learned performance, positive-control
success and statistically credible self-improvement.

Training startup correction: the descriptive environment seed `202610230301`
exceeds NumPy's accepted seed range. Before any training reset/transition, map it
modulo 2**31 in the registered runtime config. Preserve the failed launch (zero
training transitions) and launch a new run directory; learner seed is unchanged.

Prospective expert development extension (before fresh expert testing): the first
controller's large Cartesian/orientation errors saturate individual joint increments
and it fails to approach the cube in early development traces. Freeze that controller
in `expert_v1_snapshot.py`. Register one additional 12-condition paired development
batch (24 episodes), with Cartesian position/orientation step bounds and common
joint-increment scaling that preserves IK direction. No mass/force/time budget change.
Use this fixed v2 controller for the originally reserved 24-condition expert test,
regardless of its development score. This is a documented development extension,
not a rescue of or replacement for the original negative pilot evidence.
