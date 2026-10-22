# Proprioceptive guard development: a new prospective development stage

Stage A (temporal exploration, 96 training +32 validation episodes) selected hold10.
Validation success was 1/16 original vs3/16 candidate, but joint-limit samples rose
48→71: rollback. That gate remains failed, with zero heldout episodes. It will not
be reused for selecting or scoring another candidate.

Training-only joint decomposition found 29/30 hold10 violations in fingers, compared
with 20/21 for original. New hypothesis: opening on predicted empty-gripper lower-limit
approach may reduce these samples while retaining successful grasps. This is a heuristic,
not a safety proof, and may hurt grasping. Actuator limits and environment remain fixed.

New guarded-1 snapshots extend temporal-1 with an enabled flag, finger margin [0,.01]m,
and lookahead 0/1/2 control steps. Named finger indices come from the live action
mapping. At each step expose only measured finger q, qdot, lower limits and dt to the
controller. After temporal action transformation, if a close command is requested and
min(q,q+lookahead*dt*qdot) < lower_limit+margin for either finger, output binary open +1.
Otherwise keep the temporal action. No object mass, conditions, seeds, reward or test
feedback enters this controller. Log the proprioceptive inputs for independent replay.

Commit this plan and implementation before physics. Use 8 entirely new training seeds
(generator 202610221301), same stratified .8–3.2kg distribution. Six fixed candidates:
guard2; hold10guard2; hold10guard6; hold10guard10look2; guard6look2; hold10guard3look0.
The suffix is margin in mm; default lookahead=1. Two groups each run identity and three
candidates on paired conditions, randomized order: 64 physical training episodes.
Rank by successes, fewer joint-limit samples, then smaller parameter intervention;
identity replays are averaged to eight-condition scale and remain in the ranking.

If a nonidentity candidate is selected, register 16 entirely new validation conditions
(generator 202610221401, uniform .8–3.2kg), original vs selected candidate, 32 episodes.
Gate stays strict: success count must increase AND joint-limit samples must not increase.
No candidate retuning or changing thresholds after validation. Reserve every episode
before launch, retain failures, preserve source hashes and all raw actions/states.

This stage has a fixed maximum of 96 real episodes, zero heldout episodes. Only a gate
promotion can justify a separately preregistered multi-seed matched-control efficacy study.
The previous stages' conditions are development data and will not be included in that
study's test score. Preserve both earlier rollbacks and this stage's full results.
