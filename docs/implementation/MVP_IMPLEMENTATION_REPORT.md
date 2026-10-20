# PhysicalEvoBench MVP implementation report

Status: **IN PROGRESS — physical MVP not accepted**. No physical success rate or Evolution Gain
is reported. Synthetic CPU fixtures are never included in benchmark results.

## Repository

- Repository: https://github.com/ros-claw/PhysicalEvoBench (public, created during this session).
- Default branch: `main`; implementation branch: `implementation/mvp`.
- No MVP release or acceptance merge has been performed.
- Local bootstrap commit: `8aa5d1f` (initial documentation, license and Arena submodule).
- Pull request and CI evidence will be recorded after the implementation branch is pushed.

## Environment and immutable dependencies

- Host: Ubuntu 22.04 family, Linux 6.8.0-138-generic, x86_64, approximately 125 GiB RAM.
- GPUs: four NVIDIA RTX A6000, 49,140 MiB each; driver 595.91.07, reported CUDA capability 13.2.
  Existing GPU processes were left running. See [GPU inspection](../evidence/p0/nvidia-smi.txt).
- Project CPU environment: uv-managed Python 3.12.13, `uv.lock` committed.
- Arena: `release/0.3.1`, pinned to `c7edf3a9d5d8276565208f72422f8f8a0806d6cf`.
- Isaac Lab submodule: `91a0906f93802eb859192dcb0bca879f891e92d6`.
- Arena native lock selects Isaac Sim 6.1.0.0, isaaclab package 17.0.2, Torch 2.11.0+cu128,
  RSL-RL 5.4.1. The installation prose's 6.0.1 / 3.0.0 differs; see compatibility notes.
- HF revision: `01277d4f4944174ea7eb4c701d962a078b75c8ce`.
- Official `model_1999.pt` SHA256:
  `babbbfd363f894443ffe494f26c5b6e0485fb35d4f5480c088295c23fc2a13aa`.
- Weights downloaded outside the repository, not redistributed. Detailed hashes:
  [checkpoint provenance](../evidence/p0/checkpoint-provenance.json).

## Gates

| Gate | Status | Evidence and remaining work |
| --- | --- | --- |
| P0 official physical episode | IN PROGRESS | Public repository, pinned upstream and model provenance established; full native runtime installation underway. Initial launch failed because its interpreter did not yet exist. |
| P1 calibrated mass task | BLOCKED by P0 | Source API inspected; deterministic split and skill schemas have CPU tests. Actual mass/inertia readback, pilot distribution and replay pending. |
| P2 real feedback update | BLOCKED by P0/P1 | Train-feedback allowlist, constrained proposals, budgeting and paired promotion gate implemented and CPU-tested. No physical candidate executed. |
| P3 heldout comparison | BLOCKED by P2 | No scores, real episodes, HTML benchmark or demonstration video yet. |
| P4 reproducible release | BLOCKED by physical gates | CPU CI and documentation prepared. Full fresh-clone GPU reproduction, acceptance merge and v0.1 release pending. |

## Executed commands and evidence

| Command | Result | Evidence |
| --- | --- | --- |
| `nvidia-smi` | exit 0; RTX hardware present | `docs/evidence/p0/nvidia-smi.txt` |
| `git ls-remote ... refs/heads/release/0.3.1` | exit 0; expected commit | pinned gitlink and upstream checkout |
| `gh repo create ros-claw/PhysicalEvoBench --public ...` | exit 0 | `docs/evidence/p0/github-repository.json` |
| `uv sync --python 3.12 --extra dev --extra models` | exit 0 | root `uv.lock` |
| `uv run python scripts/download_checkpoint.py` | exit 0 | `docs/evidence/p0/checkpoint-download.log` |
| recursive upstream submodule setup | first run intentionally stopped, exit 143, to skip unrelated LFS payloads; source-only retry exit 0 | `submodules.log`, `submodules-source-only.log`, `submodule-revisions.txt` under `docs/evidence/p0/` |
| upstream `uv sync --locked --extra dev` | installation underway | `docs/evidence/p0/arena-uv-sync.log` |
| `uv run physicalevobench smoke --config configs/smoke.yaml --gpu 0 --run-dir runs/p0-zero-initial` | exit 2, INFRA_FAILURE; no runtime interpreter, zero episodes | `docs/evidence/p0/smoke-initial.log`; local raw `runs/p0-zero-initial/` |
| `uv run physicalevobench doctor ...` | exit 2 in CPU environment, expected missing simulator packages | `docs/evidence/p0/doctor-current.json` |
| `uv run pytest -q` | 16 passed | CPU contract and subprocess boundary checks; synthetic inputs only |
| `uv run ruff check physicalevobench tests scripts/download_checkpoint.py` | exit 0 | local lint verification |

## Implemented protocol boundaries

`SkillSpec` is immutable, validates finite bounded gains and uses canonical SHA256 snapshots.
The initial gain is 1.0; no pretrained model has been intentionally weakened. Only arm gain
is currently proposed: unverified gripper parameters are excluded.

Typed training feedback rejects unknown fields (including physical mass) and any split other
than train. The deterministic proposer references source failure IDs and explicitly states
that its gain hypothesis is unproven. Budget reservation fails before an over-budget rollout.
The paired validation gate rejects mismatched conditions and infrastructure failures, and rolls
back ties. A one-request JSON subprocess updater rejects heldout feedback and mass fields;
its returned skill hash is revalidated by CPU tests. The complete physical experiment
orchestration is not implemented yet. Local malicious-code isolation is not claimed.

The official runner is launched as a separate OS process, preserves raw logs and reports
process completion separately from physical acceptance. It will not overwrite previous runs.

## Experimental results

| Group | Heldout episodes | Successes | Success rate | Evolution Gain |
| --- | --- | --- | --- | --- |
| Frozen | not_run | not_measured | not_measured | — |
| Feedback-updated | not_run | not_measured | not_measured | not_measured |
| Budget-matched random | not_implemented | not_measured | not_measured | not_measured |

No representative physical failure/update case is available. No candidate validation, skill
diff, final freeze, paired statistics or true simulation video exists. Collision and joint-limit
measurements are not implemented and must not be reported as zero.

## Limitations and next priorities

The candidate mass range [0.05, 0.40] kg remains uncalibrated; formal distributions and budgets
have not been frozen. Official state observations contain object/target state. Public manifests
are not a secret test service. GPU numerical reproducibility and pretrained-policy compatibility
have not yet been validated.

1. Complete the pinned runtime and pass official zero-action and pretrained lift rollouts.
2. Verify physical mass/inertia and action mapping, then calibrate and freeze conditions.
3. Execute a genuine failure–proposal–validation–freeze–paired-test loop and preserve full evidence.

Conclusion: the CPU protocol foundation is testable; the physical adaptation chain has not
yet run. There is no evidence at this point of positive physical self-improvement.
