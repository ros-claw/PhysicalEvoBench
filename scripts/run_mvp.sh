#!/usr/bin/env bash
set -euo pipefail
exec uv run physicalevobench run --config configs/mvp.yaml --agents frozen,feedback_search "$@"
