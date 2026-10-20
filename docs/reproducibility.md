# Reproducibility

Use Linux x86_64 and an RTX GPU. Keep project CPU tools and Arena's full GPU runtime in
separate virtual environments. The existing machine's Isaac Lab checkout has local changes;
it is not used for the pinned experiment.

`scripts/setup_arena.sh` initializes recursive submodules, verifies Arena's commit and runs
`uv sync --locked --extra dev` in the upstream checkout without editing tracked files.
This may download many gigabytes. The upstream lockfile is the source of dependency versions.
The setup script defaults `UV_CACHE_DIR` to the project disk's `.cache/uv` rather than the
user's home partition. Ensure adequate free space for both extracted cache and runtime.
Build temporaries also default to `.cache/tmp` on that disk through `TMPDIR`.
Submodule setup skips Git LFS payloads: nested GR00T dependencies contain unrelated humanoid
checkpoints. Their source commits are still initialized recursively. Fetch any task-required
LFS assets explicitly rather than downloading every optional model or dataset. Franka's
official policy is obtained separately by the checkpoint script.
The launch commands set the Isaac Sim EULA environment variables as documented upstream.
For an existing checkout, never switch Arena to main or independently upgrade Isaac Lab.

The fixed Arena commit contains a documentation discrepancy: installation prose says
Isaac Sim 6.0.1 / Lab 3.0.0, while `uv.lock` selects Isaac Sim 6.1.0.0, `isaaclab` package
17.0.2, Torch 2.11.0+cu128 and RSL-RL 5.4.1. Reproduce the lock first; do not silently substitute
the host's Sim 6.0.1. Native installation readiness and a successful physical episode are
separate gates.

Download models using `scripts/download_checkpoint.sh`. The script resolves a requested HF
revision to its immutable commit, downloads outside the repository and records file SHA256s
in `provenance.json`. To reproduce this setup use `--revision 01277d4f4944174ea7eb4c701d962a078b75c8ce`.
The expected `model_1999.pt` hash is
`babbbfd363f894443ffe494f26c5b6e0485fb35d4f5480c088295c23fc2a13aa`.

The smoke wrapper uses one environment and a single CUDA-visible GPU, preserves raw upstream
JSONL and refuses to overwrite an existing run directory. GPU PhysX replay may have numerical
nondeterminism even with identical seeds. No deterministic replay claim has been validated yet.

To diagnose the actual GPU interpreter, run the doctor module under Arena's Python with
this project's root on `PYTHONPATH`; the default `uv run` doctor describes the CPU environment.

For long installs, `uv run python scripts/continue_p0.py --gpu 0 --run-dir runs/p0-bootstrap`
performs pinned sync, native doctor, zero-action and pretrained lift in order. It writes each
step's exact command and exit code, stops on errors, and leaves physical acceptance for review.
Use `--wait-pid` only when an existing installer for this checkout is already running.
