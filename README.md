# PhysicalEvoBench

Benchmarking Self-Improving Embodied Agents through Physical Feedback.

PhysicalEvoBench measures whether physical failures lead to an executable skill change and whether
its frozen version helps on independent conditions. The initial v0.1 track uses Franka Lift Object in
Isaac Lab-Arena/PhysX, object mass perturbations, frozen official RSL-RL weights and bounded arm gain.
Later experiments add actual PPO weight updates. The tasks use privileged state observations.

## Core benchmark development (2026-10-27)

The new [Benchmark Card](BENCHMARK_CARD.md) separates parameter adaptation from bounded
skill-program learning, with matched budgets, actual-model tools, frozen artifacts,
independent test instances and artifact deletion. T0 keeps the calibrated ten-second
score; T1 Pick–Transport–Place has its own feasibility and independent reference gate.
This is a development Alpha contract, not a claim of stable learning or a new release.

[Lightweight participant quickstart](docs/core/QUICKSTART.md) ·
[Registered stage budgets](docs/core/CORE_PROTOCOL_20261027.md) ·
[Program schema](docs/core/S_PROGRAM_SCHEMA.md).

```bash
uv run physicalevobench-core smoke                         # CPU only, zero physics
uv run physicalevobench-core audit --run-dir /path/to/run # offline evidence recomputation
```

## State-based reference calibration (later on 2026-10-26)

**A separately versioned ten-second reference task passed finite independent calibration.**
The state-based teacher verifies pose, bilateral contact and object-follow before lifting;
bounded joint-error integration addresses the heavy-load tracking failure. Independent
v2 effective holds are **6/6 at 0.1 kg and 5/6 at 0.4 kg**, with **0/12** for its
open-gripper control and no registered joint-position violations. V1's failed heavy-load
confirmation and the original five-second failure are preserved. This stage ran **64
diagnostic episodes**, including four separately budgeted parameter-activation checks.
No PPO training or actual autonomous-Agent comparison ran; this is a calibrated reference,
not proof of stable self-evolution.

[本轮完整报告](docs/implementation/STATE_REFERENCE_实施报告_20261026.md) ·
[Frozen reference protocol](docs/experiments/STATE_REFERENCE_V2_PROTOCOL_20261026.md) ·
[Evidence](docs/evidence/state-reference-20261026).

## v0.2 physical diagnosis and calibration (2026-10-26)

**The reference calibration failed; actual Agent learning comparisons remain gated off.**
This stage added live physical target bounds, post-physics substep recording and terminal
capture before autoreset, without changing historical scores. It completed **153 diagnostic
episodes, 35,333 control steps and 141,332 physics samples**, with zero new training.
The selected representative cases showed fewer severe events under bounded targets but
no task completions; target bounds did not prevent every actual state violation.
The 96-episode startup/reset experiment had a zero-success floor. Original, geometric
teacher and open-gripper reference arms each achieved **0/12 effective holds** in the
36-episode calibration, so W3 did not pass. The narrow artifact/tool API is CPU-tested;
it is not an executed autonomous Agent or evidence of self-evolution.

[阶段实施报告](docs/implementation/V02_阶段实施报告_20261026.md) ·
[Physical diagnosis](docs/experiments/V02_PHYSICS_DIAGNOSIS.md) ·
[Calibration and stop gate](docs/experiments/V02_CALIBRATION.md) ·
[Publicly re-audited evidence](docs/evidence/v02-physics-20261026).

## Three-seed, three-round confirmation (registered 2026-10-24)

**Stable self-evolution was not established. All five registered scientific gates failed.**
The completed fixed study ran **18 PPO jobs, 11,059,200 real PhysX training transitions
and 4,610 evaluation episodes**. All 18 actual actor/critic/optimizer audits passed;
changed parameters alone do not establish improvement. All nine continual candidates
were rejected, with a failed finger maximum-depth guard in every decision. All
three final continual trajectories therefore retained the original checkpoint.

| Learning seed | Frozen /128 | Identity /128 | Final retained continual /128 | Retained restart /128 |
| --- | --- | --- | --- | --- |
| 0 | 34 | 32 | 36 | 36 |
| 1 | 29 | 35 | 34 | 57 |
| 2 | 24 | 26 | 23 | 27 |

Pooled final retained success is **93/384**, versus **87/384**
frozen and **93/384** identity replay. These continual models are identical;
the differences are replay variation. The identical-policy safety replay also failed
the registered guard in **3/3** trajectories, exposing sensitivity to sampled
safety variability. No failed candidate was retroactively promoted.

A separately preregistered **576-episode diagnosis on 192 new paired conditions**
tested every trajectory's latest raw candidate, without selecting the best run or
adding training: original **46/192**, raw continual **68/192**,
latest raw restart **68/192**. Raw continual vs original: **+11.46 pp**,
adjusted conditional interval **[+0.52, +22.40] pp**.
Per-trajectory raw continual successes are 16→32, 11→28 and 19→8 (each out of 64); the third trajectory regresses. Raw continual vs latest raw restart has zero pooled difference, with adjusted conditional interval [-10.94, +10.94] pp. This diagnostic cannot rescue failed retention, multi-round stability or safety gates.

All arms use the registered +/-1000 numerical action envelope and original official
lift success; sustained holding is unmeasured in these early-terminating episodes.
The separate full-horizon holding calibration failed (original 0/12 low-speed holds).
Earlier numerical failures and all costs remain published: another **3,686,400 training
transitions and 52 diagnostic/calibration episodes**. Including the raw diagnosis,
this investigation completed **14,745,600 training transitions and 5,238 evaluation
or diagnostic episodes**, kept in separate inferential studies.

[Main results](docs/experiments/STABILITY_RESULTS_20261024.md) ·
[Raw-policy diagnosis](docs/experiments/RAW_POLICY_PROBE_RESULTS_20261024.md) ·
[Preregistration](docs/experiments/STABILITY_PROTOCOL_V3_20261024.md) ·
[Verified main evidence](docs/evidence/stability-20261024) ·
[Verified diagnostic evidence](docs/evidence/raw-policy-probe-20261024).
Public archive verification recomputes raw outcomes, all training transition values
and statistics; licensed model tensor checks were performed locally and are excluded
from public weight redistribution. Intervals are conditional on three fixed learned
trajectories, with no population or unlimited self-evolution guarantee.

## Historical v0.1.0 baseline

**v0.1.0 ran two real 48-episode executions, including a fresh clone. Promotion and rollback both work;
stable skill improvement has not been demonstrated.** See the [implementation report](docs/implementation/MVP_IMPLEMENTATION_REPORT.md).

| First run | Frozen | Final agent after rollback |
| --- | --- | --- |
| Heldout successes | 3 / 16 | 4 / 16 |
| Retained skill | original | same original |

The +6.25 pp observed difference is replay variability between identical retained skills, **not evidence
of evolution**. This release demonstrates the evaluation protocol; it does not establish algorithmic
superiority or general self-improvement. The prospective follow-up below adds a budget-matched random control.

The [fresh-clone execution](docs/evidence/experiments/reproduction-001/report/index.html) promoted the
candidate and measured 2/16 vs 3/16 on test, with a paired interval of [-12.5, +25] pp. That interval
includes degradation, and test joint-limit samples increased. Both executions use the same protocol
seed; they are not an independent-seed effectiveness study.

[Real HTML report](docs/evidence/experiments/mvp-seed20261021-001/report/index.html) ·
[Metrics](docs/evidence/experiments/mvp-seed20261021-001/report/metrics.json) ·
[Real camera video](docs/evidence/experiments/mvp-seed20261021-001/videos/baseline_candidate_rejected.mp4) ·
[中文说明](README.zh-CN.md)

## Prospective confirmation (2026-10-22)

A preregistered follow-up ran **528 real episodes**, three new learning seeds and 72 distinct
heldout conditions. Both feedback-guided search and budget-matched random search rolled back
in all three seeds. The final policy therefore remained identical in all four test arms:
Frozen **13/72**, identity replay **17/72**, feedback **13/72**, random **14/72**.
These differences are replay variation; **self-improvement was not confirmed**. All three
independent physical artifact audits passed. See the [results and limits](docs/experiments/CONFIRMATION_RESULTS_20261022.md),
[preregistration](docs/experiments/CONFIRMATION_PREREGISTRATION.md) and
[complete per-seed evidence archives](docs/evidence/confirmation-20261022-001).

```bash
uv run python scripts/run_confirmation.py --output runs/confirmation-new --gpus 0 1 2
uv run python -m physicalevobench.evaluation.confirmation_audit --study-dir runs/confirmation-new
```

The launcher requires a clean committed worktree and uses the fixed protocol config. Replaying
published seeds is reproduction; a new effectiveness study requires newly registered seeds and
heldout conditions. The original v0.1.0 evidence and release tag remain unchanged.

## Temporal and guarded development (224 additional episodes)

Two prospectively bounded development stages expanded the wrapper to gripper hold,
arm smoothing and predictive finger-limit guards. The first validation improved
successes **1/16 → 3/16**, but joint-limit samples rose **48 → 71**: rollback.
The guarded stage measured **5/16 → 5/16**, samples **40 → 38**: rollback because
successes did not increase. **No formal heldout episode was launched.** A proposed
696-episode confirmation remains gated off; its budget is not an executed result.

See [development progress](docs/experiments/ADAPTATION_PROGRESS_20261022.md),
[temporal evidence](docs/evidence/temporal-development-20261022-001) and
[guarded evidence](docs/evidence/guarded-development-20261022-001). These are frozen-weight
controller adaptations; no model-weight training or demonstrated self-evolution is claimed.

## Calibration and real weight learning (2026-10-23)

Train-only PPO completed **614,400 real transitions** and 200 PPO iterations (20 minibatch optimizer steps per iteration).
Validation promoted the changed model (6/24 → 8/24). The initial 32 fresh heldout
pairs scored **4/32 original versus 10/32 learned**, +18.75 pp (conditional interval
[+3.125, +34.375] pp; exact one-sided p=0.0352).

Post-hoc order stratification motivated a fixed **96-episode confirmation** on
**48 new conditions**, using separate per-policy workers with crossed GPU allocation.
It scored **12/48 versus 15/48**, +6.25 pp, interval **[-12.5, +25] pp**, p=0.3318.
**Stable improvement was not confirmed.** Both studies remain visible; neither
changed weights nor the first significant result proves robust self-evolution.

A known degraded gripper control scored 0/12 versus original 24/24 at 0.1 kg;
the geometry expert failed (0/24 versus 4/24). Fixed-source process replays still
differed on 2/12 success flags despite matching recorded initial states/actions.
Aggregate safety counts improved, while one finger's maximum limit depth worsened.

See [full results and limits](docs/experiments/CALIBRATION_LEARNING_RESULTS_20261023.md),
[protocol and amendments](docs/experiments/CALIBRATION_LEARNING_PROTOCOL_20261023.md),
and [complete raw evidence](docs/evidence/calibration-learning-20261023-001).
Cost: **422 completed evaluation/diagnostic/demo episodes**, separately from 2,467
completed training episodes and 128 unfinished training rollouts. Trained weights
remain outside the repository under their inherited licensing terms.

## CPU quickstart

```bash
git clone https://github.com/ros-claw/PhysicalEvoBench.git
cd PhysicalEvoBench
uv sync --locked --extra dev --extra models
uv run pytest -q
uv run physicalevobench doctor --config configs/lift_mass_v0.yaml
```

`doctor` automatically selects an installed Arena runtime and otherwise inspects the current Python.
It exits 2 when required packages or weights are missing. Use `--current-interpreter` to inspect CPU
tools explicitly; that environment intentionally does not include Isaac Sim.

## Real GPU reproduction

Use Linux x86_64, an RTX GPU and sufficient disk space. Arena is pinned to
`c7edf3a9d5d8276565208f72422f8f8a0806d6cf`, with a separate native runtime. Its complete lock currently
selects Isaac Sim 6.1.0.0. Installation downloads large dependencies; see [reproducibility](docs/reproducibility.md).

```bash
bash scripts/setup_arena.sh
bash scripts/download_checkpoint.sh
uv run physicalevobench smoke --config configs/smoke.yaml --gpu 0 --run-dir runs/zero-001
uv run physicalevobench smoke --config configs/smoke.yaml --gpu 0 --policy rsl_rl --run-dir runs/lift-001
bash scripts/run_mvp.sh --gpu 0 --run-dir runs/mvp-001
uv run physicalevobench audit --run-dir runs/mvp-001
uv run physicalevobench report --run-dir runs/mvp-001
```

`run` executes actual training, a subprocess proposal, paired validation, promotion/rollback, freezing,
32 heldout episodes, independent artifact audit and HTML generation. It never substitutes mock results.
Existing run directories and unsafe resume are rejected. A no-candidate or incomplete evidence chain
is not accepted by the audit. Reports preserve negative findings and unmeasured sensor fields.

The frozen mass distribution is 0.8–3.2 kg, calibrated before formal testing from 14 paired pilot episodes.
Formal budgets are 8 train, 8 validation and 32 test episodes. Rendered demo replays are separate from
these budgets and scores. The recorded video uses an actual 84×84 wrist camera, enlarged for viewing;
it shows an original skill and rejected candidate, not a promoted improvement.

## Boundaries and licensing

The trusted worker owns physical parameters, seeds, environment objects and scores. The updater sees
only serialized train feedback; its process ends before testing. Public manifests are heldout evaluation,
not a secret anti-cheating server or an OS sandbox against malicious local code. Initial states replayed
within 1e-6, but GPU physical trajectories and outcomes varied. Collision sensing is not implemented.

Project code is Apache-2.0. NVIDIA model weights have separate non-commercial terms and are downloaded
outside this repository. We do not redistribute them. See [NOTICE](NOTICE.md), [protocol](docs/benchmark_protocol.md)
and [contributing](CONTRIBUTING.md).
