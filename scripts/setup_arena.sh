#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.cache/uv}"
export TMPDIR="${TMPDIR:-$PWD/.cache/tmp}"
mkdir -p "$UV_CACHE_DIR" "$TMPDIR"
GIT_LFS_SKIP_SMUDGE=1 git -c url.https://github.com/.insteadOf=git@github.com: \
  submodule update --init --recursive
actual_commit=$(git -C external/IsaacLab-Arena rev-parse HEAD)
test "$actual_commit" = c7edf3a9d5d8276565208f72422f8f8a0806d6cf
cd external/IsaacLab-Arena
uv sync --locked --extra dev
OMNI_KIT_ACCEPT_EULA=YES ACCEPT_EULA=Y .venv/bin/python -c \
  'import isaaclab_arena; print(isaaclab_arena.__file__)'
