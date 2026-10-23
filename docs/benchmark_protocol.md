# PEB-Lift-Mass-v0 protocol and current evidence

The evaluation task is the pinned upstream Franka **joint-position** Lift Object
in PhysX: unchanged robot, actuator gains/effort limits, 50 Hz and five seconds.
The official success predicate is instantaneous object-to-command distance below
0.05 m. It does not certify a stable grasp or a post-success holding interval.
The original model observes state, not pure vision.

## Versioned studies

| Study | Conditions and purpose | Recorded evidence |
| --- | --- | --- |
| v0.1.0 MVP | 0.8–3.2 kg; 4 train, 4 validation, 16 heldout pairs | Two 48-episode executions; identical protocol seed; stable improvement not shown |
| 2026-10-22 confirmation | 3 learning seeds, 8 train, 8 validation, 24 heldout per seed | 528 real episodes, feedback and random search rolled back in all seeds |
| Temporal/guarded development | Fresh training and 16-pair validation for each stage | 224 real development episodes, both rollback; no new formal heldout |
| 2026-10-23 calibration/learning | Measurement control, same-hardware geometry controller, process replay, PPO | 422 evaluation/diagnostic/demo episodes + 614,400 training transitions; initial gain not confirmed by isolated workers; [results](experiments/CALIBRATION_LEARNING_RESULTS_20261023.md) |

The 0.8–3.2 kg distribution was selected from a 14-episode, two-seed sensitivity
pilot. That pilot did **not** prove learnability, strong-expert headroom or robust
safety calibration. The earlier 0.05–0.4 kg range was a superseded pilot proposal.
Original results and release hashes remain unchanged.

## Information and budget boundaries

Train, validation and heldout condition IDs and simulator seeds are disjoint.
Evaluator-owned manifests retain mass truth. Updaters receive only explicitly
typed training feedback, never heldout outcomes or environment references. The
PPO track additionally receives public observations and dense training rewards.
Its training mode disables success termination; its completed training episodes
must not be mixed with official evaluation success counts.

Freeze source, recipe and physical budget before execution. Reserve evaluation
attempts before each rollout. Parallel PPO uses a separately stated transition
budget, reserved before each vector step; report completed training episodes,
initial and unfinished rollouts separately. Infrastructure errors preserve logs,
return codes and all completed evidence; they are not relabeled robot failures.
A serialization boundary is not an OS sandbox against malicious local code.

## Candidate acceptance and independent evaluation

Historical wrapper gates require strictly greater paired validation success and
no increase in historical sampled joint-limit counts. Ties roll back. Weight
adaptation uses the same strict validation rule in this prospective feasibility
study. Freeze the retained snapshot/decision before fresh paired heldout physics.
A rejected candidate retains the original hash. Identical-policy replay differences
are not adaptation gains. Changed weights alone are not improved performance.

Report counts, paired discordances, uncertainty, sample size and learning-seed
scope. Feedback-specific superiority requires a budget-matched no-feedback search
control. PPO versus a frozen model tests this learner's adaptation, not whether
feedback is superior to an equal-training-budget alternative. A single learning
seed does not establish robust self-evolution.

## Safety and reproducibility limits

The historical safety statistic counts pre-step joint coordinates outside live
hard limits by more than 0.001 coordinate units: radians for arm joints, metres
for fingers. It is exposure-dependent and is not an incident count. New diagnostic
records preserve this count and add per-joint depth, integrated depth, sampled
duration, any-violation episodes and per-1000 joint-sample rates. All are reported;
no post-hoc metric substitution changes historical accept/rollback decisions.
Collisions and violations between samples remain **not measured**.

Compare full recorded initial observations/velocities, first actions and subsequent
trajectories when diagnosing replay variation. Matching selected initial positions
alone does not prove complete simulator reset. A fresh-process comparison cannot
uniquely attribute variation to GPU nondeterminism. Public heldout manifests are
not a secret test service.

Implementation tests and artifact audits establish code/evidence consistency.
Scientific calibration additionally needs measurement sensitivity, credible task
headroom, adequate power and independent learned-policy evaluation. Neither an
engineering gate nor a successful smoke run establishes those properties.

See [v0.1 report](implementation/MVP_IMPLEMENTATION_REPORT.md),
[confirmation results](experiments/CONFIRMATION_RESULTS_20261022.md), and
[development progress](experiments/ADAPTATION_PROGRESS_20261022.md).
