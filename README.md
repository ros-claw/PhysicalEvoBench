# PhysicalEvoBench

Benchmarking Self-Improving Embodied Agents through Physical Feedback.

PhysicalEvoBench measures whether physical failures lead to an executable skill change and whether
its frozen version helps on independent conditions. The first track uses Franka Lift Object in
Isaac Lab-Arena/PhysX, object mass perturbations, frozen official RSL-RL weights and bounded arm gain.
It is a **state-observation skill-adaptation harness**, not model-weight learning or pure vision.

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

Train-only PPO completed **614,400 real transitions** and 200 optimizer iterations.
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
