# Stable official-task adaptation: preregistered v3 confirmation

Status before launch: NOT_RUN. This is a new registration, not a repaired success
claim for any previous attempt. All conditions, budgets and gates are frozen before
training. The original task specification asks whether physical feedback improves
the official pretrained lift policy, not whether that policy can hold an object
nearly motionless. This protocol restores that distinction explicitly.

## Earlier negative results remain part of the record

- v1 attempt 001: two real diagnostic episodes, xyzw goal-audit convention error,
  zero training/validation/test. Raw records and the failed registration are public.
- v1 attempt 002: six first-round jobs, **3,686,400 transitions**, 1,200 optimizer
  iterations, two diagnostics, zero validation/test. The third continual seed had
  value loss infinity at iterations 112/113 after actions reached 1.487e14 and
  rewards -9.206e20. Five jobs passed the finite-loss audit. All six final actor and
  critic tensors were finite, but that does not make the training trajectory stable.
- v2 full-horizon holding calibration: **24 real episodes**. Original policy reached
  the goal 12/12 but met low-speed 0.30-second holding 0/12; forced-open-gripper was
  0/12 on both. The registered holding calibration FAILED. The v2 confirmation is
  **NOT_RUN**, with no training or formal validation/test. Do not reinterpret its
  physical holding failures as successes under v3.

Holding was an additional stronger task introduced during this investigation, not
the original benchmark success definition. The v3 primary metric is fixed here
before a fresh confirmation, not changed after reading confirmation outcomes.
Every result must publish the earlier numerical and holding failures alongside v3.

## Primary task and numeric containment

Task: original upstream Franka lift, PhysX, 50 Hz, five-second limit, mass uniform
over **0.8–3.2 kg**, original success predicate and original success termination.
Frozen checkpoint SHA256:
`babbbfd363f894443ffe494f26c5b6e0485fb35d4f5480c088295c23fc2a13aa`.
Arena remains unmodified at `c7edf3a9d5d8276565208f72422f8f8a0806d6cf`.

All training/evaluation arms share the v2 numerical envelope: every finite proposed
action is clipped componentwise to **[-1000,+1000] raw action units** before the
unchanged upstream action manager. Proposed and applied actions are both retained.
The next observation's last action and the unchanged action-rate penalty refer to
the applied action. PPO likelihoods use its sampled proposal. Nonfinite proposals
or losses stop the run. This is numerical containment, not a joint, torque, contact,
or hardware safety guarantee. New ID: **PEB-Lift-Mass-NumericalEnvelope-v1**.
Do not pool these results with earlier unbounded-interface studies.

Official success can terminate immediately; sustained holding is **NOT_MEASURED**
in this confirmation. A positive result cannot be advertised as stable object
holding, which failed the separate stricter calibration.

## Prerequisite measurement calibration

24 fresh physical episodes: 12 paired 0.1 kg conditions, original checkpoint versus
forced-open-gripper degradation. Two blocks of six conditions, per-policy native
processes, GPU 2/3 allocation crossed. Independent raw audit, matching initial
physical state/public observation/velocity and unchanged original model hash.
Require original official success >=10/12 and forced-open-gripper official success
0/12. This shows sensitivity to a known large degradation; it is not an oracle for
the heavy distribution or assurance of small-effect detection. Failure blocks v3.
Calibration results never reach the updater and are not formal confirmation scores.

## Independent learning and private promotion

Three independent learned trajectories, three rounds each. In each round both a
continual and an equal-budget restart lane receive **200 PPO iterations ×24 vector
steps ×128 environments =614,400 transitions**. Exactly 18 jobs and **11,059,200
transitions**. Continual lanes resume preceding raw candidate weights and optimizer;
restart lanes reload the original every round. Neither next input checkpoint is
selected using private validation. Every candidate and rollback remains inspectable.

The learner starts at learning rate 1e-4, fixed within a round. Its train-only rule
halves the next rate if last-quarter mean public reward <=1.01 times first-quarter
mean reward, floor 1e-5. Both lane types use this rule from their own prior training
feedback. No human changes the recipe between rounds. The RPC contains only public
policy/task observations, rewards, dones and timeouts; no mass truth, environment
seed, private validation or test outcomes. Config fields are checkpoint/output,
learner seed, iteration count and rate. This is an API contract, not an adversarial
filesystem sandbox. Training archive observations are stored losslessly as 25
states per 24-step chunk; audit reconciles every transition and unfinished rollout.

After each candidate freeze, **64 new paired private validation conditions** compare
candidate and current retained incumbent. Four blocks of 16, separate policy native
processes, each arm rotates across all four GPUs. Same budget for both algorithms.
Promote only for strictly more official successes, no increase in raw or normalized
sampled hard-joint violations, and no per-joint maximum depth worsening beyond
2 mm fingers /0.01 rad arm. Total **2,304 validation episodes**. Margins are declared
engineering tolerances, not a safety guarantee. All decisions are preserved.

## Freeze, heldout design and fixed scientific gates

All six lanes finish all three rounds and freeze every retained snapshot before any
heldout launch. Each learner trajectory gets **128 fresh paired conditions**, shared
across six arms: original frozen, independent identity replay, retained continual
rounds 1/2/3, and final retained restart control. Four blocks of 32, separate native
processes per policy/block, each arm rotates over four GPUs. **2,304 heldout episodes
on 384 unique conditions**. Two additional preregistered diagnostics check integration
only. Main evaluation budget **4,610 episodes**. Every rollout is reserved before
execution; source is exported from the registered clean Git commit.

All learner/environment/validation/test seeds are fixed in registration, disjoint
from each other and prior published/local episodes, both aborted v1 registrations,
the failed holding calibration and the new official calibration. No outcome-dependent
rounds, test selection, replay exclusion or threshold changes are allowed.

Bounded stable official-task adaptation is supported only if ALL hold:

1. Each retained round beats BOTH frozen and identity controls, paired-bootstrap
   lower bound >0. Six comparisons use Bonferroni alpha=0.05/6.
2. Final official success gain >0 in EACH of the three learning trajectories versus
   both frozen controls.
3. Consecutive rounds have nonnegative point change and lower bound >=-5 percentage
   points, two comparisons at alpha=0.05/2.
4. At least two actual private-validation promotions per continual trajectory.
5. Each trajectory's final heldout safety respects the per-joint margins above,
   raw and normalized joint violation counts do not increase, and any-violation
   episode rate rises <=5 percentage points. Collisions remain NOT_MEASURED.

Use 10,000 paired condition-bootstrap draws stratified by trajectory, RNG 20261024.
Coverage is approximate and conditional on these three fixed learned trajectories;
it is not a population-of-learners confidence guarantee. Report every seed, identity
replay difference, checkpoint hash and exact discordant-pair sign-test diagnostic.
Separately report final continual vs this specific equal-budget restart control
with a 95% paired interval; superiority only if lower bound >0.

All gates pass: **STABLE_BOUNDED_TASK_ADAPTATION_SUPPORTED**, limited to this task,
numerical envelope, mass interval, three seeds and three rounds. Otherwise:
**STABLE_SELF_EVOLUTION_NOT_ESTABLISHED**. Neither outcome proves unlimited general
self-evolution or autonomous invention of a learning algorithm. Prior failed costs
and diagnostics are separately itemized and never counted as successful replication.
