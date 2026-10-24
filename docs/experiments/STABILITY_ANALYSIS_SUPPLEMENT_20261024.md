# Pre-heldout diagnostic supplement: process blocks and identity safety

Written at 2026-10-24T11:59:06 UTC, before any heldout launch. Main registration
SHA256: `2fc99ba2e4f4a0d9d8a37c58ced7cc21c27df5877d9b8fb7455cf7e15b7ac260`.
At this point six first-round training jobs and 317 validation episodes were
recorded, zero heldout episodes. Main source remains
`7fbd96ed40ad59b419ac9ce5a526bbdea310425e`.

This supplement does **not** change training, promotion, primary scientific gates,
conditions, budgets or stop rules. The fixed study continues even after negative
promotion outcomes. The following diagnostics are defined before heldout results:

1. For final retained policy vs frozen and vs identity, additionally bootstrap whole
   paired environment-process blocks within each fixed learning trajectory. Each
   trajectory has four blocks of 32 conditions. Resample four block means per
   trajectory with replacement, 10,000 draws, RNG 20261024. Report 97.5% intervals
   (alpha=0.05/2) alongside the registered per-condition intervals. Twelve paired
   block comparisons are not 384 independent process replications. This diagnostic
   checks sensitivity to within-process correlation and remains conditional on
   three fixed learned trajectories; it is not a learner-population guarantee.
2. Apply the registered final sampled-safety guard to original vs its independent
   identity replay, whose model hashes must be identical. Report each component:
   raw count, normalized count, per-joint maximum-depth margin, and any-violation
   rate margin. If identity fails a guard, report observed replay variability rather
   than attributing every failed candidate guard uniquely to learned policy damage.
   Original safety gates remain unchanged; no failed promotion is retrospectively
   overridden.
3. Publish per-seed/per-block success counts for all six arms. If primary and block
   uncertainty results disagree, state that explicitly; do not present a conditional
   per-condition interval as proof robust to process variability.

The separate private checkpoint audit also checks all actor, critic and optimizer
tensors for finiteness, unchanged original YAML metadata, actual deterministic MLP
parameter changes and agreement with archived update norms. A changed stochastic
standard deviation or optimizer serialization alone is insufficient evidence that
the deterministic evaluated network changed.
