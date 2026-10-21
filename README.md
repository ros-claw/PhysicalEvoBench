# PhysicalEvoBench

Benchmarking Self-Improving Embodied Agents through Physical Feedback.

PhysicalEvoBench measures whether physical failures lead to an executable skill change and whether
its frozen version helps on independent conditions. The first track uses Franka Lift Object in
Isaac Lab-Arena/PhysX, object mass perturbations, frozen official RSL-RL weights and bounded arm gain.
It is a **state-observation skill-adaptation harness**, not model-weight learning or pure vision.

**Two real 48-episode executions have run, including a fresh clone. Promotion and rollback both work;
stable skill improvement has not been demonstrated.** See the [implementation report](docs/implementation/MVP_IMPLEMENTATION_REPORT.md).

| First run | Frozen | Final agent after rollback |
| --- | --- | --- |
| Heldout successes | 3 / 16 | 4 / 16 |
| Retained skill | original | same original |

The +6.25 pp observed difference is replay variability between identical retained skills, **not evidence
of evolution**. This release demonstrates the evaluation protocol; it does not establish algorithmic
superiority or general self-improvement. Budget-matched random search remains future work.

The [fresh-clone execution](docs/evidence/experiments/reproduction-001/report/index.html) promoted the
candidate and measured 2/16 vs 3/16 on test, with a paired interval of [-12.5, +25] pp. That interval
includes degradation, and test joint-limit samples increased. Both executions use the same protocol
seed; they are not an independent-seed effectiveness study.

[Real HTML report](docs/evidence/experiments/mvp-seed20261021-001/report/index.html) ·
[Metrics](docs/evidence/experiments/mvp-seed20261021-001/report/metrics.json) ·
[Real camera video](docs/evidence/experiments/mvp-seed20261021-001/videos/baseline_candidate_rejected.mp4) ·
[中文说明](README.zh-CN.md)

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
