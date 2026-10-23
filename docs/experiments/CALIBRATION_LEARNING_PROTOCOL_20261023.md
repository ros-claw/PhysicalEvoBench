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

Expert actuator diagnosis, before expert test: local IK increments alone cannot
hold the gravity-enabled low-PD robot used by the benchmark (live arm stiffness
80, unlike the upstream high-PD IK embodiment which disables gravity). Preserve
v2 in `expert_v2_snapshot.py`. Register a final four-condition paired development
check, eight episodes, adding robot gravity compensation as `g(q)/live_stiffness`
to commanded joint targets. This uses the robot model, not the object mass, and
changes neither stiffness nor effort limits nor gravity. Log those terms. Freeze
this v3 algorithm for the 24-condition expert test regardless of pilot outcome;
no further development extensions in this study. Total expert development budget
is 24 + 24 + 8 = 56 completed episodes, explicitly separated from the 48 test
control episodes. These manual development corrections are not contestant learning.

Replay provenance correction: the initial sequential fresh-process supervisor
imported from the live worktree. Passive instrumentation/controller development
continued during its later worker startups, so it cannot certify one frozen source
for all fresh workers. Preserve that entire 12-attempt sequence as exploratory
runtime/provenance evidence; do not use it as the registered source-controlled
comparison. Repeat the 12 fresh-process episodes using an immutable package tree
extracted from the persistent replay's registered commit, hash-checking every source
before each startup and recording the supervisor/runtime commits separately.
This adds exactly 12 evaluation attempts. No conditions are selected or replaced
based on their outcomes. The persistent 36-episode study is unchanged.

Exploratory reset/support follow-up: two geometry-controller workers had a first
original-policy episode in which cube xy stayed fixed and z followed free fall
through the table height before the distant gripper could reach it. Subsequent
resets did not show that trajectory. Do not silently reclassify or remove those
failures. Register a targeted reproduction: both observed conditions, GPU 0 and
GPU 1, one fresh worker each, three original-policy repeats per worker (12 total).
These deliberately reused anomalous seeds diagnose cold-start/reset behavior and
cannot estimate population anomaly rates. No model/controller tuning is permitted
from this probe; report it separately from the frozen PPO efficacy study.

After efficacy scores are complete, reserve two illustrative camera replays (one
original, one frozen learned policy) on the largest-mass successful learned-policy
heldout condition. This is deliberately post-hoc demo selection, not new efficacy
evidence. Publish both camera replays regardless of outcome, with no retries or
weight changes. The two demo episodes are additional cost, excluded from the
32-pair score and all learning feedback.

## Follow-up registration after the initial heldout result

Post-hoc order stratification of the original 32 pairs found: original-first 1/19
versus learned-second 7/19; learned-first 3/13 versus original-second 3/13. This
could be sampling differences or cross-policy reset/carryover. Preserve the first
study unchanged. Register 48 **new** conditions, 96 episodes, zero further weight
updates, before running this follow-up. Two blocks of 24 pairs use separate
per-policy environment processes throughout; GPU allocation is crossed between
blocks (original 0 / learned 1, then original 1 / learned 0). Each worker processes
its paired block's conditions in the same order. Freeze source via immutable Git
snapshot and retain every startup/process/episode record. Report the 48-pair
success difference, discordant outcomes, exact one-sided p and conditional interval
separately from the earlier 32 pairs. This is a prospectively fixed confirmation
of the already trained policy, motivated by a post-hoc diagnostic; it is not an
independent learning seed, a repair of the initial score, or proof of multi-round
evolution. No outcome-dependent budget extension or weight tuning in this follow-up.
