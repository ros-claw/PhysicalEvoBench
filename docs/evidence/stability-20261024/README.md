# stability-20261024: complete independently verified physical evidence

Main scientific outcome: **STABLE_SELF_EVOLUTION_NOT_ESTABLISHED**. Fixed study completed 4,610 actual PhysX evaluation episodes and 11,059,200 training transitions. All 18 actual model/optimizer audits passed. A successful integrity audit is not a successful scientific outcome.

All three continual trajectories retained the original checkpoint after all three rounds. Same-checkpoint heldout differences are replay variability, not learning. The separate raw-final-policy diagnostic does not override failed promotions. Sustained holding and collision safety are not established.

The 33,652 raw files are split losslessly across `evidence-*.tar.gz`. Source snapshots include the preregistered runtime and delivery tools. `manifest.json` hashes every extracted file; `SHA256SUMS.json` hashes every top-level delivery file except itself. `public_reaudit.json` records fresh extraction and independent raw recomputation; `verifier_provenance.json` pins the verifier's Git source bytes. Licensed model weights and recorder files are excluded.

Reproduce the public check from the repository root, using a fresh output directory:

```bash
uv run python scripts/verify_stability_delivery.py --evidence docs/evidence/stability-20261024 --output /path/to/fresh-verification --numpy-python /path/to/python-with-numpy
```

Earlier numerical and holding-calibration failures remain published in their own evidence folders. They are not positive replications or pooled with these results.
