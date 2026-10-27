# Core pilot evidence — 2026-10-27

**Actual-model protocol completed, zero observed P gain; T1 reference failed. Formal
two-task Core is not accepted or released.** No stable self-evolution claim.

- B1:48 development episodes on4 conditions; grid and identity counts both3–4/4.
- P pilot:4 Agent learning +8 search learning +16 paired heldout =28 episodes.
  Frozen/Search/Feedback/artifact deletion each4/4. One learning trajectory/method.
- T1: initial reference0/4, forced-open0/4; sole correction0/4. Development cap12 exhausted.
- Independent T1 confirmation, S model learning, transfer and retention:NOT_RUN_GATE_FAILED.
- Total88 actual PhysX episodes,20 distinct conditions,49,016 controls,196,064 post-physics samples.
- Five actual learning-model calls:84,474 input/371 output tokens; one separate
  connectivity call13,507/15, zero learning or physics. No PPO or weight update.

`manifest.json` binds1,455 raw/derived files in four lossless data archives and ten
registered source archives. `public_delivery_audit.json` reports PASS with888 source
checks after extraction into a different directory. Weights, simulation assets and
HDF5 recorder duplicates are excluded. Model configuration/card metadata retain
upstream NVIDIA terms; see NOTICE.md and the preserved model card, not Apache relicensing.

```bash
uv run python -m physicalevobench.core.delivery verify --evidence docs/evidence/core-pilot-20261027 --output /path/to/new-extraction
```

Verification recomputes raw commands/target limits, complete exposed substeps,
terminal snapshots, state/contact guards, physical scoring, budgets, model/tool
provenance, initial-state pairing, retained artifacts and reported conclusions.
It is CPU recomputation, **not** new physics or a new independent learning run.

`source-only-core-alpha.tar.gz` is an optional lightweight code/cards/configs/CPU-test
bundle (about182kB compressed), separate from this125MiB raw evidence. CPU smoke
works without a simulator/model. Standard physical runs should use the documented
clean Git checkout with pinned native dependencies and independently obtained
licensed weights. Reusing the minimal calibration receipt is not rerunning physics.

Three cancelled-before-launch reservations and the exact zero-work prelaunch
recovery are preserved. No outcome-based physical retry, seed replacement, gate
relaxation or fabricated task-flow result occurred. New-directory CPU installation
passed13 Core tests; its prepared native runtime was **not** used for a physical
rerun because the T1 prerequisite failed.

See [完整实施报告](../../implementation/CORE_BENCHMARK_实施报告_20261027.md).
