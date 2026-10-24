# Stable adaptation v2: numerical containment, unchanged scientific gates

Status before launch: NOT_RUN. This is a new experiment, not a continuation or
successful reinterpretation of the failed v1 registration. Source and all conditions
are frozen before physics. It inherits the full design, holding definition, budgets,
learner, private gates, six heldout arms and statistical criteria of
[the original protocol](STABILITY_PROTOCOL_20261024.md), with the following explicit
changes and prerequisite. No v1 training data is reused for updates or scores.

## Recorded v1 failure

Attempt 001 completed two diagnostic episodes and exposed an xyzw audit convention
error; zero training or formal evaluation. Attempt 002 completed six first-round
training jobs: **3,686,400 transitions**, 1,200 PPO updates, two new diagnostic
episodes, and **zero validation or heldout episodes**. Five training audits passed.
The third continual trajectory failed the finite-loss audit at updates 112/113.
Its proposed actions reached 1.4871986962432e14 and dense rewards reached
-9.205734111126644e20. The value losses became positive infinity. All six jobs,
including the failed seed and unbounded action history, are retained. The final
checkpoint being finite does not make that training process numerically stable.
The registered driver stopped before private validation, as required.

## Uniform numerical action envelope

New environment ID: **PEB-Lift-Mass-Stability-v2**. All original, identity, continual
and restart arms, in training and evaluation, apply a componentwise envelope of
**[-1000, +1000] raw action units** before the unchanged upstream action manager.
This is a conservative numerical limit chosen to leave ordinary previously observed
actions unchanged while containing the observed runaway feedback. It is not a robot
joint target, torque, contact, or physical safety guarantee. Affine action mapping,
actuator configuration, task rewards, physics, observations, hardware and success
criteria remain upstream. Sampled hard-joint safety gates still apply in full.

Every finite NN proposal is recorded separately from the applied clipped action.
Nonfinite proposals stop the run; they are never replaced with a finite value.
The environment observes its actually applied action, including in its next public
last-action observation and unchanged action-rate penalty. PPO retains its sampled
proposal for likelihood calculations, as a stochastic policy followed by a fixed
environment action transformation. Independent audits reconstruct the envelope for
every saved training transition and every evaluation action. The updater's payload
schema is unchanged and contains no evaluator mass, environment seed or test score.

## Prerequisite physical measurement calibration

Before v2 confirmation starts, a separate preregistered diagnostic uses 12 fresh
0.1 kg conditions paired between the original checkpoint and a forced-open-gripper
degradation control. Both use the same envelope, full five-second horizon and new
holding metric. Separate native policy processes, independent raw audit, 24 episodes.
Require original >=8/12 holding and >=10/12 instant reaches, and open-gripper 0/12
holding. This calibrates sensitivity to a large known degradation, not small-effect
power, nor a strong oracle for the 0.8–3.2 kg confirmation distribution. Failure
blocks confirmation; do not alter the thresholds after observing it.

The main new registration uses fresh seeds excluding prior published/local runs,
both aborted v1 registrations, and this calibration. Main budgets remain
11,059,200 training transitions + 4,610 evaluation episodes. The 24 calibration
episodes and every earlier attempt are accounted separately. All final conclusions
must report the v1 numerical failure alongside the new study. A v2 positive result
would concern adaptation under this uniform numerical envelope, not stable learning
in the original unbounded action interface.
