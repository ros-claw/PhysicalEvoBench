# PhysicalEvoBench v0.1 implementation and acceptance report

**The real physical feedback–candidate–validation–freeze–heldout loop has run twice, including a fresh clone. Both promotion and rollback were exercised. Stable improvement has not been demonstrated.** All P0–P4 delivery gates passed and v0.1.0 is published.

## Repository and environment

Public repository: https://github.com/ros-claw/PhysicalEvoBench. Implementation PR: https://github.com/ros-claw/PhysicalEvoBench/pull/1, merged at `2026-10-21T02:01:06Z` as `0f88cc2225d4eba0ec8f6bddef8ccb3593348c97`. All 27 CPU tests pass locally, in the new clone and in GitHub Actions. Final implementation head `a3abebf95d1ffbbb07826571ef2e02ac2b8b0645` passed both [push CI](https://github.com/ros-claw/PhysicalEvoBench/actions/runs/39530338724) and [PR CI](https://github.com/ros-claw/PhysicalEvoBench/actions/runs/39530343516).

[v0.1.0](https://github.com/ros-claw/PhysicalEvoBench/releases/tag/v0.1.0) was published at `2026-10-21T02:03:19Z`. Its tag resolves to the merge commit above; this publication ledger is a subsequent documentation update. Actual GitHub API records are retained in `docs/evidence/p4/merged-pr-1.json` and `release-v0.1.0.json`. The downloadable evidence ZIP preserves repository-relative paths and has a separate SHA256 checksum; it excludes model weights and runtime caches.

The host has four RTX A6000 GPUs (49,140 MiB each), driver 595.91.07; rollouts use GPU 0. CPU tools and Arena have separate Python 3.12.13 environments. Native doctor passed (`docs/evidence/p0/doctor-native.json`).

| Input | Pinned value |
| --- | --- |
| Arena | `c7edf3a9d5d8276565208f72422f8f8a0806d6cf`, unmodified submodule |
| Isaac Lab gitlink | `91a0906f93802eb859192dcb0bca879f891e92d6` |
| Actual runtime packages | Isaac Sim 6.1.0.0, isaaclab 17.0.2, RSL-RL 5.4.1, Torch 2.11.0+cu128 |
| HF revision | `01277d4f4944174ea7eb4c701d962a078b75c8ce` |
| Checkpoint SHA256 | `babbbfd363f894443ffe494f26c5b6e0485fb35d4f5480c088295c23fc2a13aa` |

Versions follow upstream `uv.lock`, despite older versions in its installation prose. NVIDIA weights remain outside the repository under separate non-commercial terms and are not redistributed.

## Gates

| Gate | Status | Evidence |
| --- | --- | --- |
| P0 official physics | PASS | Zero-action: 20 steps, exit 0. Original checkpoint: one successful 62-step PhysX lift, exit 0. `docs/evidence/p0/official-zero/`, `official-lift/` |
| P1 controlled conditions | PASS | 14 paired-seed pilot episodes; actual mass and proportional inertia checks; repeated initial state matches. `docs/evidence/p1/` |
| P2 actual candidate | PASS | Train failures produced gain 1.05 candidate, real actions changed, validation tied and correctly rolled back |
| P3 independent evaluation | PASS | Two 48-episode executions, each with 16 heldout pairs and audit PASS; real HTML reports and recorded camera video |
| P4 release | PASS | New clone and new virtual environments completed full GPU run; 27 CPU tests and CI pass; PR #1 merged and v0.1.0 published |

## Execution and corrective work

The original background installation completed with exit 0. Its first smoke failed (exit 2) because the launcher dereferenced the venv interpreter symlink, bypassing `pyvenv.cfg`. A real venv regression test now checks `sys.prefix`. The next launch rejected obsolete `--headless`; the adapter now uses supported `HEADLESS=1`. Both failures are preserved under `runs/p0-bootstrap-20261021/` and `runs/p0-zero-venv-fixed/`.

Successful official commands and raw logs are copied to `docs/evidence/p0/official-zero/` and `official-lift/`. The successful checkpoint episode is seed 42, success=true, 62 steps (1.24 simulated seconds), with the original upstream completion predicate.

The first mass probe stopped on its readback assertion: changing the pre-build sampler did not change the manager-owned copy. The adapter now uses the live reset-event sampler. The second probe completed one real episode, then failed because explicit resets and stepping used inconsistent inference modes. Persistent rollouts now keep both in inference mode. These attempts are retained as infrastructure failures, not robot failures: `runs/p1-mass-pilot-001.log`, `runs/p1-mass-pilot-002.log`.

The corrected pilot (`runs/p1-mass-pilot-003/`, exit 0) tested 0.05, 0.1, 0.2, 0.4, 0.8, 1.6 and 3.2 kg with the same seeds 1000/1001 at each mass. Both seeds succeeded through 0.8 kg and failed at 1.6/3.2 kg. All 14 physical mass/inertia checks passed; replayed joint positions, object position and goal command matched exactly. See `docs/evidence/p1/physical_readback_and_replay.json`.

The home partition approached exhaustion. Only task-created cache directories with byte-identical project-disk copies were relocated, preserving original cache paths as symlinks and recovering approximately 2.7 GB. The mapping is in `docs/evidence/p0/verified-cache-relocation.json`. Unrelated simulation processes were retained.

## Formal protocol and physical update

Before formal test results were read, `configs/mvp.yaml` froze mass interval **0.8–3.2 kg**, seed **20261021**, four train conditions, four validation conditions and sixteen heldout conditions. IDs and seeds are disjoint. Training spans the interval; validation/test masses are uniform draws. The task remains original Franka joint-position lift, PhysX, 50 Hz, five-second timeout and unchanged success criterion.

The exact command was `physicalevobench run --config configs/mvp.yaml --agents frozen,feedback_search --gpu 0 --run-dir runs/mvp-seed20261021-001` (exit 0). Each attempt is reserved in a ledger before physics. Unsafe resume is refused.

Initial training produced 1/4 successes and three failures. A separate updater process received only serialized episode IDs, boolean outcomes, `task_not_completed` labels and budget. It received no environment object, mass truth or test feedback. Its exact request and response are preserved in `evolution/agent_request.json` and `agent_response.json`.

The candidate changed `arm_action_gain: 1.0 → 1.05` with unchanged model hash. Named action-manager terms resolved the seven arm coordinates and binary gripper coordinate; no unverified last-index assumption is used. Four candidate training episodes produced 1/4 successes. Actual arm actions changed by up to **8.41783142** action units.

Validation was 4/4 successes for incumbent and 4/4 for candidate, with zero sampled joint-limit violations in both. The predeclared strict-positive gain gate therefore **rolled back**. The candidate skill, hypothesis, failure references, physical traces, diff and decision are preserved. No promotion was forced.

The updater ended before heldout testing. Both final groups used retained skill SHA256 `fa6d9729759e451098bcb88ec30ad8d653d1e638222d683c86abb7b4f678f922`.

## Real scores and their limits

| Group | Successes / episodes | Rate | Retained skill |
| --- | --- | --- | --- |
| Frozen | 3 / 16 | 18.75% | original identity skill |
| Final Feedback Search after rollback | 4 / 16 | 25.00% | same original identity skill |
| Budget-matched random | not_run | not_measured | not implemented |

The nominal paired success-rate difference is **+6.25 percentage points**, with condition-bootstrap 95% interval [0, 18.75] pp. **The retained skills are identical. This difference is physical replay variability, not evidence of evolution.** There was no retained update or demonstrated algorithmic advantage. A single run and this conditional bootstrap do not establish cross-run significance.

Formal cost: **8 training + 8 validation + 32 heldout = 48 real episodes**, one candidate, zero promotions, one rollback, zero model tokens. Official smoke and pilot episodes are additional, separately identified costs. Video replays, if completed, are also separate from scores.

Finite/live-action-space checks found zero invalid test actions. Pre-step hard-joint-limit samples were **11 Frozen / 22 repeated-final** at a 0.001 coordinate-unit tolerance. The initial integration trace's rule string said “rad”; its correct meaning is joint coordinate units (rad for revolute joints, metres for prismatic fingers), clarified in current code. Raw joint positions remain unchanged. These sampled counts are not a complete safety assessment. Collision sensors were not installed: **not_measured**.

Independent audit rechecked manifests, split/seed isolation, frozen skills, budgets, raw upstream outcomes, trace lengths, physical mass, paired initial states and recomputed metrics. It passed all checks across 48 episodes and 16 test pairs. Initial masses, inertias, joints, object positions and commands matched within 1e-6, while subsequent GPU physics trajectories varied.

## Inspectable deliverables

Full real evidence is committed under `docs/evidence/experiments/mvp-seed20261021-001/`: raw action/state traces, initial conditions, upstream JSONL, split manifests, ledger, skills, proposals, gate decisions, metrics, audit and `report/index.html`. No synthetic episode is included.

`physicalevobench audit --run-dir runs/mvp-seed20261021-001` passed (exit 0); `physicalevobench report --run-dir ...` generated the real HTML report (exit 0). `pytest -q` passed 27 tests and Ruff passed. Independent audit additionally reconstructs applied actions from each hashed skill and its raw action trace; tampering with an action or a stored score is rejected by tests using copies of real recorded data.

## Fresh-clone GPU reproduction and observed variability

A new public GitHub clone at code commit `7bf0e8e7696c6a6986a5c7b7c8874135aeb16672` initialized all pinned submodules and installed separate CPU/GPU virtual environments. It reused downloaded immutable wheels and the independently downloaded checkpoint, not an existing runtime environment. Its initial git worktree was clean and source SHA256s are recorded in provenance.

`bash scripts/run_mvp.sh --gpu 0 --run-dir runs/reproduction-001` completed with exit 0, automatically auditing 48 physical episodes and generating HTML. Source, commands, logs and return codes are recorded in `docs/evidence/p4/`; full evidence is in `docs/evidence/experiments/reproduction-001/`.

This repeated the **same protocol seed and conditions**, not an independent seed study. The predeclared gate now saw 3/4 incumbent vs 4/4 candidate validation successes and joint-limit samples 13 vs 0, so it promoted the same gain-1.05 candidate. Independent test then measured:

| Execution | Frozen | Final agent | Nominal paired difference | Gate |
| --- | --- | --- | --- | --- |
| Initial | 3/16 | 4/16, unchanged skill | +6.25 pp, interval [0, 18.75] | rollback |
| Fresh clone | 2/16 | 3/16, actual gain-1.05 skill | +6.25 pp, interval [-12.5, 25] | promote |

The second result is an observed positive difference for an actually changed skill, but its interval spans degradation, and a same-skill replay already showed a difference of the same size. **This is not stable or statistically persuasive evidence of self-improvement.** Both outcomes are published without selecting the better run. The fresh test had joint-limit samples 27 vs 48, despite the validation safety gate passing; safety generalization is not established.

Total formal cost is 96 physical episodes across two executions. Official baseline (1), completed pilot episodes (15, including the interrupted probe's one result), and camera demos (2) bring the documented completed-episode total to 114. Zero-action step smoke and infrastructure initialization failures are separate overhead. Both formal runs used only 16 distinct heldout conditions; their repeated execution must not be presented as 32 independent conditions.

## Real video and acceptance

Two additional demo episodes replayed a real training failure with the original and rejected candidate. Both timed out. Their 250 actual wrist-camera frames per episode were encoded at 50 Hz, then enlarged and labeled side by side. Frames were visually inspected; no generated animation or mock imagery is used. Full demo provenance and traces are under `docs/evidence/experiments/mvp-demo-001/`; the comparison MP4 is linked in the first HTML report. Demo outcomes do not enter formal scores or agent feedback.

The doctor now automatically uses an installed Arena virtual environment; `--current-interpreter` retains explicit CPU-only diagnosis. Its selected-interpreter success is recorded in `docs/evidence/p0/doctor-cli-native.json`.

Public manifests are heldout evaluation, not a secret test server. The official policy uses privileged state observations, not pure vision. Physical mass calibration used only two pilot seeds. There is no budget-matched random comparison, so feedback-specific superiority cannot be claimed.

Next priorities:
1. Expand calibration and evaluation across independent seeds, accounting for GPU replay variability.
2. Add budget-matched random search before making feedback-specific claims.
3. Investigate out-of-validation joint-limit behavior before extending safety claims.
