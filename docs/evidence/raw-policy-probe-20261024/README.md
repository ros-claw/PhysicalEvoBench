# raw-policy-probe-20261024: complete independently verified physical evidence

Scientific role: **SEPARATE_DIAGNOSTIC_NOT_STABILITY_CONFIRMATION**. Completed 576 actual PhysX evaluation episodes on 192 new paired conditions, zero additional training. Main confirmation outcome remains **STABLE_SELF_EVOLUTION_NOT_ESTABLISHED**.

Latest raw round-3 continual/restart candidates are evaluated for all three trajectories, regardless of private validation. No best-of-run selection or retroactive promotion. Conditional task-success gains do not establish stable or safe self-evolution.

The 3,792 raw files are split losslessly across `evidence-*.tar.gz`. Source snapshots include the preregistered runtime and delivery tools. `manifest.json` hashes every extracted file; `SHA256SUMS.json` hashes every top-level delivery file except itself. `public_reaudit.json` records fresh extraction and independent raw recomputation; `verifier_provenance.json` pins the verifier's Git source bytes. Licensed model weights and recorder files are excluded.

Reproduce the public check from the repository root, using a fresh output directory:

```bash
uv run python scripts/verify_stability_delivery.py --evidence docs/evidence/raw-policy-probe-20261024 --output /path/to/fresh-verification
```

Earlier numerical and holding-calibration failures remain published in their own evidence folders. They are not positive replications or pooled with these results.
