# Contributing

Use a feature branch and a pull request. Run `uv sync --locked --extra dev`, `uv run pytest -q`
and `uv run ruff check physicalevobench tests scripts/download_checkpoint.py` before review.

Keep the upstream Arena submodule unmodified. Pin dependency changes explicitly. CPU fixtures
must be labeled synthetic and must never be included in reported physical results. Preserve
negative findings and infrastructure failures; do not silently discard episodes or exceed budgets.

Do not commit model weights, credentials, private observations or unlicensed assets. GPU
integration evidence must include commands, return codes, versions and episode provenance.
