# Temporal skill exploration: training only

Hypothesis from previously published **training** traces: repeated gripper open/close
commands and object lift-then-fall may limit the frozen policy. This does not establish
causality. Test bounded temporal wrappers without changing mass, actuator strength,
robot model, control rate, timeout or official success predicate.

A new temporal-1 skill records arm smoothing alpha in [.1,1] and binary gripper hold
in [0,250] steps; defaults are identity. Hold starts after an open command has been
seen and a later negative close command occurs at step >=15. For H steps including
that command, force -1 (closed) then resume policy control. History is reset per
episode. Arm filtering is exponential, alpha=1 is identity; the first action is
unfiltered. Raw gripper convention is verified in the pinned upstream action class.
No mass, seeds, outcomes or evaluator objects enter this controller.

Before any new rollout commit this plan and code. Use eight new training conditions,
stratified masses .8–3.2kg, generator seed 202610221101. Test nine fixed candidates:
hold 10/25/50/100/250; smoothing .5/.2; hold50+smoothing .5/.2. Three workers each
run identity and three candidates on the same eight conditions, randomized per
condition: 96 real training episodes total, zero heldout episodes. Identity replays
are additional physical baseline cost; report them separately, not as distinct
conditions. These data are exploration and cannot be cited as heldout efficacy.

Retain all attempts, actual control traces, official outcomes and budgets. Rank
candidates using training successes, then fewer sampled joint-limit violations,
then smaller parameter change. A separate validation gate (16 new conditions,
original and chosen candidate, 32 episodes) must be registered before validation
outcomes are observed. Only if that gate yields a genuine retained update will we
register another prospective multi-seed matched-control test, using entirely new
conditions. Preserve any negative gate without retuning against it. Do not reuse
previous heldout conditions for candidate selection. Original weights and upstream
source remain unchanged. This is wrapper adaptation, not model-weight learning.
