# PhysicalEvoBench

Benchmarking Self-Improving Embodied Agents through Physical Feedback.

PhysicalEvoBench measures whether an executable skill changes after physical failures, and
whether the frozen update helps on independent conditions. The first target is Franka Lift
Object in NVIDIA Isaac Lab-Arena, with object mass as the adaptation axis and frozen official
RSL-RL weights. This is a **state-observation, harness/skill adaptation track**.

**Status: implementation in progress; physical MVP not yet accepted.** CPU contract tests
are not evidence of physical success. No Evolution Gain has been measured. The first release
must demonstrate the evaluation protocol; it does not automatically establish algorithmic
superiority or general self-improvement. See the [implementation report](docs/implementation/MVP_IMPLEMENTATION_REPORT.md).

## CPU quickstart

```bash
git clone --branch implementation/mvp https://github.com/ros-claw/PhysicalEvoBench.git
cd PhysicalEvoBench
uv sync --locked --extra dev --extra models
uv run pytest -q
uv run physicalevobench doctor --config configs/lift_mass_v0.yaml
```

`doctor` exits with code 2 when dependencies or weights are missing. The CPU environment
does not include Isaac Sim. Do not interpret that result as an unsuitable GPU diagnosis.
The implementation branch is under review in draft PR #1; no MVP release is available yet.

## Real GPU setup and smoke

Arena is pinned to `c7edf3a9d5d8276565208f72422f8f8a0806d6cf`, not a floating branch.
Follow [reproducibility](docs/reproducibility.md) for its separate runtime and version caveats.

```bash
bash scripts/setup_arena.sh
bash scripts/download_checkpoint.sh
uv run physicalevobench smoke --config configs/smoke.yaml --gpu 0 --run-dir runs/zero-001
uv run physicalevobench smoke --config configs/smoke.yaml --gpu 0 --policy rsl_rl --run-dir runs/lift-001
```

Each smoke creates a new directory containing the exact command, raw console output, return
code, checkpoint hash and any upstream episode results. Existing directories are never reused.
`PROCESS_COMPLETED` is a process status; P0 still requires review of an actual nonzero-action
physical episode. Training, independent testing, report generation and videos are pending.

## Evaluation boundaries

Only the trusted worker receives simulator objects, physical mass, seeds and heldout results.
Agents receive serialized train feedback and propose constrained, hashed skills. Validation
decides promotion or rollback; heldout conditions are evaluated only after freezing. Public
manifests are held-out evaluation, not a secret anti-cheating leaderboard.

The code is Apache-2.0. NVIDIA model weights are separately licensed for non-commercial use
and downloaded outside this repository; see [NOTICE](NOTICE.md). We do not redistribute them.

[中文说明](README.zh-CN.md) · [Protocol](docs/benchmark_protocol.md) · [Contributing](CONTRIBUTING.md)
