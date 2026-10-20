#!/usr/bin/env bash
set -euo pipefail
uv sync --extra dev --extra models --locked
echo 'CPU tools installed. Install the pinned Arena runtime separately; see docs/reproducibility.md.'
