# PhysicalEvoBench implementation guidance

Read `docs/implementation/MVP_IMPLEMENTATION_REPORT.md` before continuing work. The original
Chinese implementation specifications are retained at the repository root.

- Advance physical gates P0–P4 in order. CPU fixtures and process startup are not physical
  episode evidence. Report missing results, infrastructure failures and negative gain honestly.
- Keep `external/IsaacLab-Arena` at `c7edf3a9d5d8276565208f72422f8f8a0806d6cf`
  with no tracked source changes. Extend it from `physicalevobench/`.
- Root `.venv` is for CPU tools. The separate Arena `.venv` is for pinned simulation. Never
  reuse or change unrelated running Isaac Sim sessions or locally patched Isaac Lab checkouts.
- Use `uv run pytest -q` and `uv run ruff check physicalevobench tests scripts/download_checkpoint.py`
  for CPU validation. GPU checks must preserve commands, return codes and raw episode evidence.
- Download weights outside the repository, pin HF revisions and SHA256, and retain NVIDIA
  model licensing separately from Apache-2.0 project code.
- Keep evaluator-only mass, seeds and test results outside updater payloads. Reserve every
  physical rollout before launch; freeze skills before independent paired evaluation.
- Make feature-branch PRs. No acceptance merge or v0.1 release until all physical gates pass.
