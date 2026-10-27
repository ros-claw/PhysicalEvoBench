# Core development protocol — registered before new physics

Date: 2026-10-27. Feature branch `feature/core-benchmark-alpha`, stacked on PR #8.
No new PPO, teacher optimization, dependency upgrades or retroactive old-score changes.

## B0 and B1

Freeze the normal v2 reference and shared executor. B1 has exactly one reservation of
48 physical development episodes: clearance {0.08,0.10,0.12} × close {0.20,0.45,0.70}
× four fresh conditions (two at each calibrated mass 0.1/0.4 kg) =36, plus three
identity blocks of four =12. Shuffle grid and condition order with RNG 2026102701;
insert replay blocks after grid 3,6,9. One sequential native process per block,
GPU2 shared workload recorded; no unrelated process changes. Runtime source remains the
previously calibrated c8017dd. Reserve all plans and budgets before any launch.

Decision: complete saturation routes P to interface smoke. Other contrasts remain
unconfirmed unless supported by an independent preregistration; do not use timing
alone, select a winning condition distribution, or append more teacher trials.
Continue S and T1 without demanding parameter efficacy.

## B2 and B3

One actual-model learning run, maximum eight T0 training episodes; score-only search
receives the same eight evaluation opportunities in the same editable space. Frozen
has zero learning, and all use the same starting reference. Save budget-zero and
budget-eight artifacts; sparse pilot is not a dense learning curve. Four fresh paired
heldout T0 conditions, two per mass, allocated before learning and inaccessible to the
participant. Evaluate Frozen, Search, Feedback and Feedback with initial artifact
in new native processes; reset per episode. This deletion arm does not count as a
new independent learning run. Total T0 pilot cap:16 learning +16 heldout =32.
P pilot is interface smoke if B1 does not establish learning room; do not rank it as
program evolution. Actual model tools: propose, run_trial, freeze. The model decides
candidates, hypotheses and final memory; no developer failure-to-repair lookup.

Initial model transport: generic JSON/stdin adapter; a local Codex CLI transport may
use the installed account and configured model in fresh ephemeral sessions with
shell/search/MCP disabled. This is an experimental participant, not implementation
work delegation. Record CLI/model versions, complete sanitized request/response,
usage and wall-clock. Maximum 12 model calls per task learning run, 120 seconds per
call, cumulative 250,000 reported input and 24,000 output tokens; timeout/invalid
submission consumes its call. Budget overrun invalidates the run, no free retry.
Transport preflight measured 13,507 input tokens of CLI overhead before any learning;
the input cap was fixed at 250,000 before B2 to include that overhead.
Only trusted participants; no claim of a hostile-code sandbox. A transport without
reported tokens is explicitly incomplete accounting and cannot be accepted as the
standard benchmark run. No credential contents are captured or redistributed.

## S schema and T1 bounded development

S schema v1: JSON graph, ≤16 named nodes, each has target expression, gripper,
public guard, next and timeout edges. No arbitrary code, evaluator variables or
unbounded loops. ≤2 recovery traversals, finite node timeouts and global task horizon.
Targets reference object, initial object, goal, grasp anchor or measured grasp offset;
guards include pose, bilateral nonempty grasp, probe-follow, elapsed time and release.
Strict schema tests must pass before first S physics. Fixed shared low-level executor;
program edits never change actuator, rate envelope, task score or source versions.

T1 development cap12: first four positive/forced-open pairs (8 episodes), then at most
four positive checks for a single documented feasibility correction. Initial candidate
horizon20 s; target center at initial cube XY+(0.12,0.12)m on the same tabletop;
release with both fingers ≥0.035m, cube within 0.05m horizontally and 0.025m vertically
of the public supported center height0.021m, cube linear speed≤0.10m/s, continuous span≥0.50s;
EE/cube distance≥0.06m prevents a closed grasp masquerading as release. Object must
have first lifted≥0.05m and transported≥0.08m. Goals/geometry exposed to all methods.
These are new development definitions, not a modification of T0. Freeze after feasible
reference; independent confirmation12 =six positive (three per mass) and six
forced-open. Require≥2/3 positive per mass and0/6 negative; failure stops transfer
claims and is retained. No more horizon/performance tuning beyond the development cap.

After T1 gate, execute T0→T1 zero-learning transfer for initial/Search/Feedback T0
artifacts (four fresh conditions each,12 total). Permit eight T1 training episodes
per trained method (16 total), freeze before test, test four T1 conditions for both
final artifacts (8), and re-evaluate four T0 conditions for both (8 retention).
T1/task-flow cap:12 development+12 confirmation+12 transfer+16 learning+8 test+8 retention=68.
All stage transitions depend on prior gates; no need to spend unused reservations.
Whole initial investigation cap148 =48 B1+32 T0 pilot+68 T1/task-flow. No hidden
extra physics. Infrastructure failures are separately costed; only rerun the same
condition with recorded cause, never silently replace a task failure.

## Evidence and publication

Record learning_run_id, budget_used, checkpoint_index, effective_artifact_hash,
task_id, split_id, condition_id, physical_replay_id, execution_profile for every row.
Store public skill/config/memory, participant identity, interface, execution, task
and scoring versions under a complete content hash. Preserve commands/return codes,
raw post-physics and terminal evidence, proposed and actual targets, GPU sharing.
Compute scores independently; report every learning run and signed differences.
One pilot trajectory cannot establish stable learning or mechanism superiority.

B5 deliver source-only lightweight entry point plus example evidence; historical
PPO streams optional. Independently check fresh-directory CPU installation, offline
raw-data audit and actual fresh-directory physical reproduction as distinct claims.
Feature PR only; no acceptance merge/release without task and protocol gates.

## Pre-launch T1 definition correction

The first queued T1 reservation (`peb-core-place-dev-20261027-001`) was cancelled
before any native launch (zero physical cost). B1 raw observations show reset
center z0.055m settles to z≈0.021m; reset height is not tabletop support height.
Before first T1 physics, define `core-place-h20-v2-dev` with target center z0.021m
and unchanged vertical tolerance0.025m. Preserve the cancelled reservation and
use a new registration. This corrects physical scoring, not an observed T1 failure.

## Task-flow pilot details frozen before S learning

After T1 confirmation, use `core-skill-library-1`: exact inherited T0 ReferenceSkill
plus replaceable T1 graph. Zero-B-learning transfer compares normal initial, T0
search and T0 feedback parameters composed with the same place template; label it
P→T1 parameter reuse, not T0 program learning. The S updater can edit the place
graph and inherited T0 parameters; retention dispatches the final library's exact
T0 entry through the unchanged reference executor. This avoids changing the T0
executor between pre/post-T1 tests.

There is one sequential trajectory per method, not three independent pilots.
T1 score-only search samples the initial graph plus seven preregistered template
variants: clearance[.08,.12], close minimum[.2,.7], release minimum[.2,.9], lower
offset[.002,.015], lower tolerance[.008,.025], uniform draws seed2026102707.
The seven variants additionally use preregistered structural templates: variants0/3
skip probe;1/4 release from transport height;2/5 use a0.9s elapsed lower guard;3/6
allow two recoveries and1.6s close timeout. These alter branches/guards, not just
parameters. All remain subject to the same physical constraints and scoring.
It has the same permitted library schema and eight trials as feedback; its fixed
proposal distribution is explicitly narrower than the full combinatorial program
space, so this pilot cannot isolate feedback quality from proposal quality.
No trajectory-level diagnostics enter search selection (boolean task scores only).

The S model has max12 calls,400,000 cumulative reported input tokens,36,000 output,
120s per call, fixed before S learning. Larger JSON programs account for the larger
ceiling relative to the P pilot. Both S methods have the same allowed ceilings;
actual costs, including zero-model search calls, are separately reported. Sparse
snapshots at0 and8; no invented16/32 measurements. Four paired fresh T1 conditions
are never exposed to either updater. Pre-T1 transfer results are evaluator-only,
not fed back into T1 learning or used to select conditions/configurations.

Maximum aggregate control cost is104,000 controls /416,000 exposed physics samples
(2,080 simulated seconds): B1 24,000; T0 pilot16,000; T1 phases60,000 plus
T0 retention4,000. Early termination spends fewer controls but still an episode.
Each phase reservation is exclusive within the study parent; cancelled-before-launch
T1 consumes zero physical episodes but remains in the ledger. No outcome-based
retry of the initial pilot, confirmation or task-flow is accepted.

## Pre-learning serialized context bound

Before any actual Agent learning/T1 execution, cancel queued pilot001 and its
dependent place-dev002 (zero native/model-learning cost). Their registrations and
preflight evidence remain. Re-register pilot002/place-dev003. Full lossless raw
trajectories remain archived; each model request contains every past trial outcome
but sampled state trajectories (every50 controls) only for the two most recent
trials. This fixed public context rule prevents avoidable exhaustion of the already
registered token ceilings. No learning result or heldout score existed when changed.

The two-task flow preserves each original learning_run_id and cumulative physical
learning budget from T0 through T1. T1 is a subsequent learning phase of the same
trajectory, not an additional independent learning replicate. Frozen remains
not_applicable. Artifacts and row IDs report actual consumed budget, including
early model freezes; method ceilings do not imply every method spends all eight.

## Infrastructure handoff recovery (zero T0 learning attempts)

B1 published its completed-physics status before its derived audit result was ready.
Pilot002 exited on the missing derived file before any native launch, initial skill
freeze or learning-model call. Preserve the original registration, source and exact
conditions; use explicit prelaunch recovery with an append-only receipt, not a new
learning seed/budget. T1 dev003 had already started after that terminal status; let
it finish and queue recovered T0 learning after its native worker exits. No T1
feedback is given to the T0 participant. Further confirmation/flow waits for the
actual Agent pilot. Dependent launches now require the derived result to exist.
