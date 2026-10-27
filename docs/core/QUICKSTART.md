# Core development Alpha: participate and reproduce

Status is experimental. Read BENCHMARK_CARD.md and the final implementation report
before interpreting scores. P parameter learning and S program learning are separate.
Normal v2 remains frozen; no benchmark task guarantees that an Agent improves.

## 1. Lightweight source and CPU smoke

A participant does not need historical PPO streams. Fetch only source paths with
Git's partial clone/sparse checkout (Git server must support filtering):

```bash
git clone --filter=blob:none --sparse --branch feature/core-benchmark-alpha https://github.com/ros-claw/PhysicalEvoBench.git
cd PhysicalEvoBench
git sparse-checkout set physicalevobench tests configs/core docs/core scripts
uv sync --extra dev
uv run physicalevobench-core smoke
uv run pytest -q tests/test_core.py
```

Smoke checks schemas and serialization with **zero physical episodes**. It does
not download weights, import Isaac Sim, call an LLM or certify a physical task.
For an installable source bundle, include pyproject.toml, uv.lock, physicalevobench
and the Core cards/configs; historical evidence is an optional separate download.

## 2. Standard real physical pilot

Initialize pinned Arena/Lab submodules and install the **separate** native runtime
using `scripts/setup_arena.sh`. Arena must remain at c7edf3a9d5d8276565208f72422f8f8a0806d6cf,
Lab gitlink91a0906f93802eb859192dcb0bca879f891e92d6. Read the root installation and
NVIDIA model license instructions before downloading the checkpoint. Set
`PHYSICALEVOBENCH_CHECKPOINT` to your external licensed model_1999.pt; its params/
agent.yaml must be beside it. Expected SHA256 is in configs/core/frozen_reference.json.
Never move licensed weights into the source/evidence bundle. Defaults resolve from
**your** home directory, not a developer-specific username.

B1 is a single preregistered development diagnosis, not repeated standard scoring:

```bash
uv run python -m physicalevobench.core.parameter_space --reference configs/core/frozen_reference.json --output /path/to/study-parent/peb-core-b1-new --gpu 2
uv run python -m physicalevobench.core.pilot --reference configs/core/frozen_reference.json --b1 /path/to/study-parent/peb-core-b1-new --output /path/to/study-parent/peb-core-pilot-new --gpu 2
```

Use a clean committed checkout; all launch sources are content addressed. GPU2 is
only a default; choose a GPU with room without stopping other users' processes.
The current P pilot uses the optional Codex CLI transport and its configured account;
install/login separately. Requests go through a generic serialized participant
contract, with no ROSClaw dependency. Model default gpt-6.1-terra is explicitly
recorded, not interchangeable in a same-model mechanism comparison. There is no
model call during test episodes. The heldout manifest is public evidence after the
run and must not be reused to tune a submission.

Generic providers can pass `--participant-command '["/absolute/path/to/participant"]'`
to the same pilot launcher, or use `ParticipantProcess(command=[...], model=..., ...)`:
read one request JSON from stdin; output one JSON line with exactly `response` and
`usage` (`input_tokens`,`output_tokens`). Response follows
configs/core/participant_call_schema.json. Usage must be actual provider accounting.
No shell command substitution is used to construct prompts. Returning a candidate
is not permission to read evaluator files. Only trusted participants are supported.

Task B4 is gated: run core.place_study development, then its independent confirmation
with --confirmation-development; run core.flow only after confirmation passes.
The exact registration captures the finite budget and fresh split assignments.
If task calibration fails, preserve the failure and stop transfer claims; do not
re-run confirmations on favorable seeds. See CORE_PROTOCOL_20261027.md.

## 3. Full offline audit (no simulator or model needed)

```bash
uv run physicalevobench-core audit --run-dir /path/to/extracted/study
```

This recomputes registered raw actions, actual target constraints, physical
substeps, terminal state, program commands and outcomes. It does **not** re-run
physics, reconstruct proprietary weights or create a new independent learning run.
The full public evidence delivery includes file SHA256s, source identities and
separate extraction verification. A fresh-directory CPU check and a fresh physical
execution are reported separately; neither is implied merely by a passing audit.

## Results and limits

Per-result identity includes learning_run_id, budget_used, checkpoint_index,
effective_artifact_hash, task_id, split_id, condition_id, physical_replay_id and
execution_profile. All failure/validation/model costs count. One learning run per
method is a pilot, not stable algorithm efficacy. Report initial/final/signed gain,
parameter/program space, and artifact deletion. Mass/seed truth stays evaluator-only;
state observation uses privileged simulator geometry. Normal contact and coordinate
limits are measured; tangential forces, actual solver effort and real-robot safety
are not established. Apache-2.0 project code does not relicense NVIDIA weights.
