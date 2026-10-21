#!/usr/bin/env bash
set -euo pipefail
exec uv run --extra models python scripts/download_checkpoint.py "$@"
