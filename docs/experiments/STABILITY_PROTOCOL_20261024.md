# Bounded stable adaptation: preregistered confirmation study

Status before launch: NOT_RUN. This protocol is committed before native physics.
Prior one-round evidence did not establish stable self-evolution. A positive result is
not assumed; the complete fixed study is reported even when promotion fails.

Integration attempt 001 at source aa63c0daaf6197ace152b2779a6d363e28fbd852
completed only two diagnostic episodes, zero training/validation/heldout episodes.
Independent scalar goal audit interpreted the runtime xyzw quaternion as wxyz and
stopped. Attempt 002 corrects only this audit convention and excludes every registered
seed from attempt 001. Criteria, budgets, updater and scoring thresholds are unchanged.
The failed run and its raw traces are preserved separately; no physical outcome is retried.

## Scope and immutable inputs

Three independent learner trajectories, three update rounds, original Franka joint-position
policy, PhysX, 50 Hz, five seconds, object mass uniformly sampled over 0.8–3.2 kg.
Arena remains c7edf3a9d5d8276565208f72422f8f8a0806d6cf. Base model SHA256 is
babbbfd363f894443ffe494f26c5b6e0485fb35d4f5480c088295c23fc2a13aa.
All models stay outside Git under the NVIDIA model terms. Each native process uses
a Git-exported immutable Python package. Registration fixes every seed, condition,
budget and source digest before launch, excluding published and local prior-run seeds.

This measures bounded autonomous policy/optimizer updates, not creation of new
algorithms, modification of model architecture, or indefinitely improving intelligence.

## Autonomous updater and equal-budget control

Each continual lane starts at the original checkpoint, then continues its previous raw
candidate weights and optimizer, regardless of private promotion. Each restart lane
starts at the original checkpoint every round. Both receive exactly 200 PPO updates
of 24 vector steps in 128 environments each round, with fresh registered learner and
environment seeds. Total: 18 jobs, **11,059,200 training transitions**. Episodes ending
inside those transitions and unfinished rollouts are independently reconciled.

Learning rate starts at 1e-4, fixed within each round. The learner halves the next rate
when mean public reward in the last quarter is at most 1.01 times the first quarter;
floor 1e-5. Restart lanes use the same rule from their preceding train-only feedback.
No human edits or hidden mass, environment seed, validation/test scores reach this
rule. Updater RPC receives only policy/task observations, rewards, done and timeout
flags. The configuration contains model paths, learner seed, iteration count and rate.
This is an auditable API contract, not a filesystem security sandbox.

After each update, 64 new paired private validation conditions compare incumbent
and candidate in separate per-policy native processes. Same allocation for both
algorithms: **2,304 validation episodes**. Promote only when holding successes strictly
increase, instant successes do not decrease, sampled joint violations and normalized
joint violation frequency do not increase, and no joint's maximum depth worsens by
more than 2 mm (fingers) or 0.01 rad (arm). These explicit engineering margins do
not mean safety is established. Rollbacks and raw candidates are retained. Validation
decisions never choose the next training checkpoint or learning rate.

## Full-horizon holding measurement

New environment ID: **PEB-Lift-Mass-Stability-v1**. Success termination is disabled
using the upstream training-mode switch, with learning disabled during evaluation.
Drop and five-second terminations remain. The previous official benchmark is unchanged.
Upstream training-mode success is always false and is preserved as such.

Primary success: object center within strictly 0.05 m of the commanded world-frame
goal AND translational speed at most 0.2 m/s for consecutive pre-step samples spanning
at least 0.30 seconds. At dt=0.02 this requires **16 samples**, not 15. The span is
(sample count - 1) times dt. Only observed pre-step states are scored; no terminal
auto-reset state or repeated video frame extends a hold. No secure-contact or
between-sample stability claim is made. Also report any instantaneous goal reach,
crosschecked against the pinned upstream evaluation predicate each sample.

Raw evidence includes actions, public observations, object position/velocity, robot
base pose, command, transformed goal, joint positions/velocities and upstream episode
records. Independent CPU audit reconstructs the goal transform, holding and safety.
Training streams store initial+24 resulting observations per chunk losslessly, avoiding
duplicate before/after arrays; SHA256 and transition continuity remain auditable.

## Freeze and independent heldout tests

All rounds for both algorithms finish and every retained snapshot is frozen before
any heldout launch. Each learning seed gets 128 new paired conditions, shared across
six arms: original frozen, independent identity replay of the original, continual
retained rounds 1/2/3, and final retained restart control. Total **2,304 heldout episodes**
on 384 unique conditions. Every arm/block gets its own native process, blocks of 32
conditions rotate GPU assignment. Initial physical state equality is independently
checked for every pair. A preliminary two-episode diagnostic checks only integration,
never selects parameters or counts in validation/test. Total evaluation budget: **4,610**.

## Fixed decision criteria

Call bounded stable adaptation supported only if ALL hold:

1. Each retained round beats BOTH frozen and identity controls, lower paired-bootstrap
   bound strictly positive. Six comparisons use Bonferroni alpha=0.05/6.
2. Final holding gain is strictly positive in EACH learning seed versus both controls.
3. Consecutive rounds have nonnegative point change and lower bound >= -5 percentage
   points, two comparisons at alpha=0.05/2.
4. At least two actual private-validation promotions occur in each continual lane.
5. Per-seed final heldout sampled safety respects depth margins above, raw and normalized
   joint violation counts do not increase, and any-violation episode rate rises <=5 pp.
   Invalid/nonfinite actions are infrastructure failure; collisions remain NOT_MEASURED.

Use 10,000 stratified paired condition-bootstrap draws with fixed RNG seed 20261024.
Intervals are conditional on these three learned trajectories; they do not provide a
population-of-learners confidence statement. Report each seed individually. The
non-regression margin expresses an operational tolerance, not proof of monotonicity.
Separately report final continual vs equal-budget restart with a 95% paired interval;
advantage is supported only if its lower bound is positive. This is superiority to
this specific control, not the best possible optimizer.

Any failed gate means **STABLE_SELF_EVOLUTION_NOT_ESTABLISHED**. Do not pool earlier
studies, suppress failed seeds, retry physical outcomes, weaken thresholds, or add
outcome-dependent rounds. Infrastructure failures retain reservation/evidence and
stop this registered run; fixes require a documented new registration.
