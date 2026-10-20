.PHONY: test doctor
test:
	uv run pytest -q
	uv run ruff check physicalevobench tests scripts
doctor:
	uv run physicalevobench doctor --config configs/lift_mass_v0.yaml
